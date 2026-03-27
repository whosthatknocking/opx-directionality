from __future__ import annotations
# pylint: disable=too-many-instance-attributes

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


NORMALIZED_BAR_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class NormalizedMarketData:
    symbol: str
    timeframe: str
    provider: str
    bars: pd.DataFrame

    def as_frame(self) -> pd.DataFrame:
        missing = [column for column in NORMALIZED_BAR_COLUMNS if column not in self.bars.columns]
        if missing:
            raise ValueError(f"normalized market data is missing columns: {missing}")
        frame = self.bars.loc[:, list(NORMALIZED_BAR_COLUMNS)].copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        return frame.sort_values("timestamp").reset_index(drop=True)


@dataclass(frozen=True)
class ValidationIssue:
    stage: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class FeatureSet:
    gap_pct: float
    first_5m_return: float
    first_10m_return: float
    first_15m_return: float
    first_15m_range_pct: float
    first_15m_close_vs_open: float
    price_vs_vwap_pct: float
    opening_volume_multiple: float
    opening_range_break_status: str
    gap_hold_or_fade: str
    candle_body_to_range_ratio: float
    intraday_high_low_position: float
    previous_day_return: float
    previous_day_close_location_in_range: float
    three_day_return: float
    five_day_return: float
    atr_normalized_recent_move: float
    average_first_15m_return: float
    average_first_15m_volume: float
    average_trend_persistence: float
    first_15m_return_minus_qqq: float
    first_15m_return_minus_spy: float
    gap_pct_minus_qqq_gap: float
    gap_pct_minus_spy_gap: float

    def as_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass(frozen=True)
class FactorContribution:
    name: str
    score: int
    rationale: str


@dataclass(frozen=True)
class SignalResult:
    ticker: str
    signal_time: datetime
    bias: str
    confidence: int
    regime: str
    option_posture: str
    raw_score: int
    factors: dict[str, float | str]
    factor_summary: list[dict[str, str | int]]
    signal_price: float | None = None
    status: str = "ok"
    reason: str | None = None
    validation_state: str = "valid"
    validation_issues: list[dict[str, str]] = field(default_factory=list)
    realized_close: float | None = None
    realized_return_pct: float | None = None
    realized_outcome: str | None = None
    directional_hit: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signal_time"] = self.signal_time.isoformat()
        return payload


@dataclass(frozen=True)
class SignalRunRecord:
    run_id: str
    run_timestamp: datetime
    trade_date: str
    signal_time_et: str
    provider_name: str
    engine_version: str
    config_version: str
    config_fingerprint: str
    tickers: list[str]
    signal_time_reached: bool
    completion_rate: float = 0.0
    validation_state: str = "valid"
    validation_issues: list[dict[str, str]] = field(default_factory=list)
    selection_status: str = "candidate"
    selection_reason: str = "awaiting_canonical_selection"
    log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["run_timestamp"] = self.run_timestamp.isoformat()
        return payload


@dataclass
class BatchRunResult:
    run: SignalRunRecord
    signals: list[SignalResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "signals": [signal.to_dict() for signal in self.signals],
        }
