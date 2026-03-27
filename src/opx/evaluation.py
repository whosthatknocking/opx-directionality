from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import pandas as pd

from opx.models import BatchRunResult, SignalResult
from opx.providers.base import MarketDataProvider


def evaluate_canonical_batches(
    batches: list[BatchRunResult],
    provider: MarketDataProvider,
    now: datetime | None = None,
) -> list[BatchRunResult]:
    if not batches:
        return []

    current_time = now or datetime.now().astimezone()
    canonical_batches = [
        batch
        for batch in batches
        if batch.run.selection_status in {"canonical", "partial_canonical"}
    ]
    if not canonical_batches:
        return batches

    tickers = sorted(
        {
            signal.ticker
            for batch in canonical_batches
            for signal in batch.signals
            if signal.status == "ok" and signal.signal_price is not None
        }
    )
    if not tickers:
        return batches

    earliest_trade_date = min(
        date.fromisoformat(batch.run.trade_date)
        for batch in canonical_batches
    )
    daily_cache = {
        ticker: provider.fetch_daily(ticker, min_date=earliest_trade_date).as_frame()
        for ticker in tickers
    }

    updated = []
    canonical_ids = {batch.run.run_id for batch in canonical_batches}
    for batch in batches:
        if batch.run.run_id not in canonical_ids:
            updated.append(batch)
            continue
        signals = [
            _evaluate_signal(
                signal,
                trade_date=batch.run.trade_date,
                daily_frame=daily_cache.get(signal.ticker),
                now=current_time,
            )
            for signal in batch.signals
        ]
        updated.append(BatchRunResult(run=batch.run, signals=signals))
    return updated


def _evaluate_signal(
    signal: SignalResult,
    trade_date: str,
    daily_frame: pd.DataFrame | None,
    now: datetime,
) -> SignalResult:
    if signal.status != "ok" or signal.signal_price is None or daily_frame is None:
        return signal

    trade_day = date.fromisoformat(trade_date)
    if trade_day >= now.date():
        return signal

    matched = daily_frame[pd.to_datetime(daily_frame["timestamp"]).dt.date == trade_day]
    if matched.empty:
        return signal

    close_price = float(matched["close"].iloc[-1])
    realized_return_pct = _pct_change(close_price, float(signal.signal_price))
    return replace(
        signal,
        realized_close=close_price,
        realized_return_pct=realized_return_pct,
        realized_outcome=_outcome_label(realized_return_pct),
        directional_hit=_directional_hit(signal.bias, realized_return_pct),
    )


def _pct_change(value: float, base: float) -> float:
    if base == 0:
        return 0.0
    return ((value - base) / base) * 100


def _outcome_label(realized_return_pct: float) -> str:
    if realized_return_pct > 0:
        return "positive"
    if realized_return_pct < 0:
        return "negative"
    return "flat"


def _directional_hit(bias: str, realized_return_pct: float) -> bool | None:
    if bias == "bullish":
        return realized_return_pct > 0
    if bias == "bearish":
        return realized_return_pct < 0
    return None
