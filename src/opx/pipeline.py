from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from opx.config import EngineConfig
from opx.features.compute import build_feature_set, resolve_signal_timestamp
from opx.models import BatchRunResult, SignalResult, SignalRunRecord
from opx.providers import DataUnavailableError, create_provider
from opx.runtime_logging import append_aggregate_run_log, setup_run_logger
from opx.signals.rule_engine import score_signal


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
            signal_time_et=config.signal_time_et,
            provider_name=provider.name,
            engine_version=config.engine_version,
            config_version=config.config_version,
            tickers=config.tickers,
            log_path=str(run_log_path),
        )
    )

    logger.info("starting run provider=%s signal_time=%s tickers=%s", provider.name, signal_timestamp.isoformat(), ",".join(config.tickers))
    benchmark_intraday = {
        symbol: provider.fetch_intraday(symbol, current_time)
        for symbol in {config.benchmark_primary, config.benchmark_secondary}
    }
    benchmark_intraday.setdefault("QQQ", benchmark_intraday.get(config.benchmark_primary))
    benchmark_intraday.setdefault("SPY", benchmark_intraday.get(config.benchmark_secondary))

    for ticker in config.tickers:
        try:
            intraday = provider.fetch_intraday(ticker, current_time)
            daily = provider.fetch_daily(ticker)
            features = build_feature_set(intraday, daily, benchmark_intraday, signal_timestamp)
            result = score_signal(ticker, signal_timestamp, features, config.scoring)
            logger.info(
                "ticker=%s status=ok bias=%s confidence=%s raw_score=%s",
                ticker,
                result.bias,
                result.confidence,
                result.raw_score,
            )
        except (DataUnavailableError, ValueError, KeyError) as exc:
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
            )
            logger.warning("ticker=%s status=unavailable reason=%s", ticker, exc)
        batch.signals.append(result)

    append_aggregate_run_log(
        config.logging.directory,
        config.logging.aggregate_filename,
        (
            f"run_id={batch.run.run_id} "
            f"timestamp={batch.run.run_timestamp.isoformat()} "
            f"provider={batch.run.provider_name} "
            f"tickers={','.join(batch.run.tickers)} "
            f"ok={sum(1 for signal in batch.signals if signal.status == 'ok')} "
            f"unavailable={sum(1 for signal in batch.signals if signal.status != 'ok')}"
        ),
    )
    return batch
