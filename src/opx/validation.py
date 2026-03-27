from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from opx.config import EngineConfig
from opx.models import (
    BatchRunResult,
    FeatureSet,
    NormalizedMarketData,
    SignalResult,
    ValidationIssue,
)


EASTERN = ZoneInfo("America/New_York")
VALID_BIASES = {"bullish", "bearish", "neutral"}
VALID_REGIMES = {"trend_continuation", "mean_reversion", "choppy"}
VALID_STATUSES = {"ok", "unavailable"}
VALID_RANGE_BREAK = {"break_above", "break_below", "inside_range"}
VALID_GAP_BEHAVIOR = {"holding", "fading", "mixed"}


def validate_market_data(
    dataset: NormalizedMarketData,
    signal_timestamp: datetime,
    minimum_bars: int,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    frame = dataset.as_frame()

    if frame.empty:
        return [
            ValidationIssue(
                stage="data",
                code="empty_dataset",
                message=f"{dataset.symbol} returned no {dataset.timeframe} rows",
            )
        ]

    timestamps = pd.to_datetime(frame["timestamp"])
    if timestamps.dt.tz is None:
        issues.append(
            ValidationIssue(
                stage="data",
                code="naive_timestamps",
                message=f"{dataset.symbol} has naive timestamps",
            )
        )
    if not timestamps.is_monotonic_increasing:
        issues.append(
            ValidationIssue(
                stage="data",
                code="unordered_timestamps",
                message=f"{dataset.symbol} timestamps are not sorted",
            )
        )

    if dataset.timeframe == "intraday":
        cutoff = signal_timestamp.astimezone(EASTERN)
        available = frame[timestamps <= cutoff]
        if len(available) < minimum_bars:
            issues.append(
                ValidationIssue(
                    stage="data",
                    code="insufficient_intraday_bars",
                    message=(
                        f"{dataset.symbol} has {len(available)} intraday bars "
                        "before the signal cutoff"
                    ),
                )
            )
    elif dataset.timeframe == "daily" and len(frame) < minimum_bars:
        issues.append(
            ValidationIssue(
                stage="data",
                code="insufficient_daily_history",
                message=f"{dataset.symbol} has only {len(frame)} daily rows",
            )
        )

    return issues


def validate_feature_set(features: FeatureSet) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    payload = features.as_dict()
    for field_name, value in payload.items():
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            issues.append(
                ValidationIssue(
                    stage="feature",
                    code="non_finite_feature",
                    message=f"{field_name} is not finite",
                )
            )

    if features.opening_range_break_status not in VALID_RANGE_BREAK:
        issues.append(
            ValidationIssue(
                stage="feature",
                code="invalid_opening_range_break",
                message=features.opening_range_break_status,
            )
        )
    if features.gap_hold_or_fade not in VALID_GAP_BEHAVIOR:
        issues.append(
            ValidationIssue(
                stage="feature",
                code="invalid_gap_behavior",
                message=features.gap_hold_or_fade,
            )
        )
    if features.intraday_high_low_position < 0.0 or features.intraday_high_low_position > 1.0:
        issues.append(
            ValidationIssue(
                stage="feature",
                code="intraday_position_out_of_range",
                message=str(features.intraday_high_low_position),
            )
        )
    return issues


def validate_signal(signal: SignalResult) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if signal.status not in VALID_STATUSES:
        issues.append(ValidationIssue(stage="signal", code="invalid_status", message=signal.status))
    if signal.bias not in VALID_BIASES:
        issues.append(ValidationIssue(stage="signal", code="invalid_bias", message=signal.bias))
    if signal.regime not in VALID_REGIMES:
        issues.append(ValidationIssue(stage="signal", code="invalid_regime", message=signal.regime))
    if signal.status == "unavailable" and not signal.reason:
        issues.append(
            ValidationIssue(
                stage="signal",
                code="missing_unavailable_reason",
                message=signal.ticker,
            )
        )
    if not 0 <= signal.confidence <= 100:
        issues.append(
            ValidationIssue(
                stage="signal",
                code="confidence_out_of_range",
                message=str(signal.confidence),
            )
        )
    return issues


def apply_signal_validation(signal: SignalResult, issues: list[ValidationIssue]) -> SignalResult:
    if not issues:
        return signal
    state = "invalid" if signal.status == "unavailable" else "partial"
    return replace(
        signal,
        validation_state=state,
        validation_issues=[issue.to_dict() for issue in issues],
    )


def finalize_batch_validation(
    batch: BatchRunResult,
    config: EngineConfig,
    signal_timestamp: datetime,
    benchmark_issues: list[ValidationIssue],
) -> BatchRunResult:
    run_issues = list(benchmark_issues)
    if not batch.run.signal_time_reached:
        run_issues.append(
            ValidationIssue(
                stage="run",
                code="ran_before_signal_time",
                message=signal_timestamp.isoformat(),
            )
        )

    attempted = {signal.ticker for signal in batch.signals}
    missing_tickers = sorted(set(config.tickers) - attempted)
    if missing_tickers:
        run_issues.append(
            ValidationIssue(
                stage="run",
                code="missing_ticker_attempts",
                message=",".join(missing_tickers),
            )
        )

    ok_count = sum(1 for signal in batch.signals if signal.status == "ok")
    completion_rate = ok_count / len(config.tickers) if config.tickers else 0.0

    if ok_count == 0:
        run_issues.append(
            ValidationIssue(
                stage="run",
                code="no_successful_signals",
                message=batch.run.run_id,
            )
        )

    validation_state = "valid"
    if run_issues or any(signal.validation_state != "valid" for signal in batch.signals):
        validation_state = "partial"
    if ok_count == 0 or any(issue.code == "missing_benchmark_data" for issue in run_issues):
        validation_state = "invalid"

    selection_status = "candidate"
    selection_reason = "awaiting_canonical_selection"
    if not batch.run.signal_time_reached:
        selection_status = "diagnostic"
        selection_reason = "ran_before_signal_time"
    elif validation_state == "invalid":
        selection_status = "diagnostic"
        selection_reason = "invalid_run"

    run = replace(
        batch.run,
        completion_rate=completion_rate,
        validation_state=validation_state,
        validation_issues=[issue.to_dict() for issue in run_issues],
        selection_status=selection_status,
        selection_reason=selection_reason,
    )
    return BatchRunResult(run=run, signals=batch.signals)
