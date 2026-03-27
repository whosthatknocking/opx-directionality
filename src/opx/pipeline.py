from __future__ import annotations
# pylint: disable=too-many-locals

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from opx.canonical import apply_canonical_selection
from opx.config import EngineConfig, config_fingerprint
from opx.features.compute import build_feature_set, resolve_signal_timestamp
from opx.models import BatchRunResult, SignalResult, SignalRunRecord, ValidationIssue
from opx.providers import DataUnavailableError, create_provider
from opx.runtime_logging import append_aggregate_run_log, setup_run_logger
from opx.signals.rule_engine import score_signal
from opx.validation import (
    apply_signal_validation,
    finalize_batch_validation,
    validate_feature_set,
    validate_market_data,
    validate_signal,
)


def _signal_price_from_intraday(intraday, signal_timestamp: datetime) -> float:
    frame = intraday.as_frame()
    eligible = frame[frame["timestamp"] <= signal_timestamp]
    if eligible.empty:
        raise ValueError("not enough bars before signal time")
    return float(eligible["close"].iloc[-1])


def run_daily_engine(config: EngineConfig, now: datetime | None = None) -> BatchRunResult:
    current_time = now or datetime.now().astimezone()
    signal_timestamp = resolve_signal_timestamp(current_time, config.signal_time_et)
    run_id = str(uuid4())
    logger, run_log_path = setup_run_logger(config.logging.directory, run_id)
    provider = create_provider(config)

    batch = BatchRunResult(
        run=SignalRunRecord(
            run_id=run_id,
            run_timestamp=current_time,
            trade_date=signal_timestamp.date().isoformat(),
            signal_time_et=config.signal_time_et,
            provider_name=provider.name,
            engine_version=config.engine_version,
            config_version=config.config_version,
            config_fingerprint=config_fingerprint(config),
            tickers=config.tickers,
            signal_time_reached=current_time >= signal_timestamp,
            log_path=str(run_log_path),
        )
    )

    logger.info(
        "starting run provider=%s signal_time=%s tickers=%s",
        provider.name,
        signal_timestamp.isoformat(),
        ",".join(config.tickers),
    )

    benchmark_intraday = {}
    benchmark_issues: list[ValidationIssue] = []
    for symbol in (config.benchmark_primary, config.benchmark_secondary):
        try:
            dataset = provider.fetch_intraday(symbol, current_time)
            issues = validate_market_data(dataset, signal_timestamp, minimum_bars=3)
            if issues:
                benchmark_issues.extend(issues)
                raise ValueError("; ".join(issue.message for issue in issues))
            benchmark_intraday[symbol] = dataset
        except (DataUnavailableError, ValueError) as exc:
            benchmark_issues.append(
                ValidationIssue(
                    stage="run",
                    code="missing_benchmark_data",
                    message=f"{symbol}: {exc}",
                )
            )

    benchmark_intraday.setdefault("QQQ", benchmark_intraday.get(config.benchmark_primary))
    benchmark_intraday.setdefault("SPY", benchmark_intraday.get(config.benchmark_secondary))

    for ticker in config.tickers:
        try:
            if benchmark_issues:
                raise ValueError("; ".join(issue.message for issue in benchmark_issues))

            intraday = provider.fetch_intraday(ticker, current_time)
            daily = provider.fetch_daily(ticker)
            data_issues = validate_market_data(intraday, signal_timestamp, minimum_bars=3)
            data_issues.extend(validate_market_data(daily, signal_timestamp, minimum_bars=6))
            if data_issues:
                raise ValueError("; ".join(issue.message for issue in data_issues))

            features = build_feature_set(intraday, daily, benchmark_intraday, signal_timestamp)
            feature_issues = validate_feature_set(features)
            if feature_issues:
                raise ValueError("; ".join(issue.message for issue in feature_issues))

            result = score_signal(ticker, signal_timestamp, features, config.scoring)
            result = replace(
                result,
                signal_price=_signal_price_from_intraday(intraday, signal_timestamp),
            )
            signal_issues = validate_signal(result)
            result = apply_signal_validation(result, signal_issues)
            logger.info(
                "ticker=%s status=ok validation=%s bias=%s confidence=%s raw_score=%s",
                ticker,
                result.validation_state,
                result.bias,
                result.confidence,
                result.raw_score,
            )
        except (DataUnavailableError, ValueError, KeyError) as exc:
            issue = ValidationIssue(stage="signal", code="ticker_unavailable", message=str(exc))
            result = SignalResult(
                ticker=ticker,
                signal_time=signal_timestamp,
                bias="neutral",
                confidence=0,
                regime="choppy",
                option_posture="unavailable",
                raw_score=0,
                factors={},
                factor_summary=[],
                status="unavailable",
                reason=str(exc),
                validation_state="invalid",
                validation_issues=[issue.to_dict()],
            )
            result = apply_signal_validation(result, validate_signal(result))
            logger.warning(
                "ticker=%s status=unavailable reason=%s",
                ticker,
                exc,
            )
        batch.signals.append(result)

    batch = finalize_batch_validation(batch, config, signal_timestamp, benchmark_issues)
    batch = apply_canonical_selection([batch])[0]
    append_aggregate_run_log(
        config.logging.directory,
        config.logging.aggregate_filename,
        (
            f"run_id={batch.run.run_id} "
            f"timestamp={batch.run.run_timestamp.isoformat()} "
            f"provider={batch.run.provider_name} "
            f"selection_status={batch.run.selection_status} "
            f"validation_state={batch.run.validation_state} "
            f"completion_rate={batch.run.completion_rate:.2f} "
            f"tickers={','.join(batch.run.tickers)} "
            f"ok={sum(1 for signal in batch.signals if signal.status == 'ok')} "
            f"unavailable={sum(1 for signal in batch.signals if signal.status != 'ok')}"
        ),
    )
    return batch
