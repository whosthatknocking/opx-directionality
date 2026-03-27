from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from opx.models import FeatureSet, NormalizedMarketData


EASTERN = ZoneInfo("America/New_York")


def build_feature_set(
    intraday: NormalizedMarketData,
    daily: NormalizedMarketData,
    benchmark_intraday: dict[str, NormalizedMarketData],
    signal_timestamp: datetime,
) -> FeatureSet:
    intraday_frame = _to_indexed_frame(intraday)
    daily_frame = _to_indexed_frame(daily)
    benchmark_frames = {symbol: _to_indexed_frame(dataset) for symbol, dataset in benchmark_intraday.items()}

    signal_bar = _slice_to_signal_time(intraday_frame, signal_timestamp)
    today = signal_bar[signal_bar.index.date == signal_timestamp.astimezone(EASTERN).date()]
    if len(today) < 3:
        raise ValueError("not enough bars before signal time")

    prior_close = float(daily_frame["close"].iloc[-2])
    open_price = float(today["open"].iloc[0])
    last_close = float(today["close"].iloc[-1])
    first_3 = today.iloc[:3]

    qqq_day = _select_day(benchmark_frames["QQQ"], signal_timestamp)
    spy_day = _select_day(benchmark_frames["SPY"], signal_timestamp)

    vwap_series = ((today["close"] * today["volume"]).cumsum() / today["volume"].replace(0, pd.NA).cumsum()).ffill()
    high_15 = float(first_3["high"].max())
    low_15 = float(first_3["low"].min())
    range_15 = max(high_15 - low_15, 1e-9)
    body_ratio = abs(float(first_3["close"].iloc[-1]) - open_price) / range_15
    cumulative_volume = float(today["volume"].sum())

    avg_first_15m_return, avg_first_15m_volume, avg_trend_persistence = _historical_intraday_averages(intraday_frame)
    atr = _average_true_range(daily_frame, window=5)
    recent_move = float(daily_frame["close"].iloc[-1] - daily_frame["close"].iloc[-4])
    intraday_high = float(today["high"].max())
    intraday_low = float(today["low"].min())

    first_15m_return = _pct_change(float(first_3["close"].iloc[-1]), open_price)
    gap_pct = _pct_change(open_price, prior_close)

    return FeatureSet(
        gap_pct=gap_pct,
        first_5m_return=_pct_change(float(today["close"].iloc[0]), open_price),
        first_10m_return=_pct_change(float(today["close"].iloc[1]), open_price),
        first_15m_return=first_15m_return,
        first_15m_range_pct=(range_15 / open_price) * 100,
        first_15m_close_vs_open=((float(first_3["close"].iloc[-1]) - open_price) / open_price) * 100,
        price_vs_vwap_pct=_pct_change(last_close, float(vwap_series.iloc[-1])),
        opening_volume_multiple=cumulative_volume / max(avg_first_15m_volume, 1.0),
        opening_range_break_status=_opening_range_break(last_close, high_15, low_15),
        gap_hold_or_fade=_gap_behavior(open_price, prior_close, last_close),
        candle_body_to_range_ratio=body_ratio,
        intraday_high_low_position=(last_close - intraday_low) / max(intraday_high - intraday_low, 1e-9),
        previous_day_return=_pct_change(float(daily_frame["close"].iloc[-2]), float(daily_frame["close"].iloc[-3])),
        previous_day_close_location_in_range=_close_location(
            float(daily_frame["close"].iloc[-2]),
            float(daily_frame["high"].iloc[-2]),
            float(daily_frame["low"].iloc[-2]),
        ),
        three_day_return=_pct_change(float(daily_frame["close"].iloc[-1]), float(daily_frame["close"].iloc[-4])),
        five_day_return=_pct_change(float(daily_frame["close"].iloc[-1]), float(daily_frame["close"].iloc[-6])),
        atr_normalized_recent_move=recent_move / max(atr, 1e-9),
        average_first_15m_return=avg_first_15m_return,
        average_first_15m_volume=avg_first_15m_volume,
        average_trend_persistence=avg_trend_persistence,
        first_15m_return_minus_qqq=first_15m_return - _benchmark_first_15m_return(qqq_day),
        first_15m_return_minus_spy=first_15m_return - _benchmark_first_15m_return(spy_day),
        gap_pct_minus_qqq_gap=gap_pct - _benchmark_gap(benchmark_frames["QQQ"], signal_timestamp),
        gap_pct_minus_spy_gap=gap_pct - _benchmark_gap(benchmark_frames["SPY"], signal_timestamp),
    )


def resolve_signal_timestamp(now: datetime, signal_time_et: str) -> datetime:
    eastern_now = now.astimezone(EASTERN)
    hours, minutes = [int(part) for part in signal_time_et.split(":")]
    return datetime.combine(eastern_now.date(), time(hours, minutes), tzinfo=EASTERN)


def _to_indexed_frame(dataset: NormalizedMarketData) -> pd.DataFrame:
    frame = dataset.as_frame().copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame.set_index("timestamp").sort_index()


def _slice_to_signal_time(frame: pd.DataFrame, signal_timestamp: datetime) -> pd.DataFrame:
    eastern_ts = signal_timestamp.astimezone(EASTERN)
    return frame[frame.index <= eastern_ts]


def _select_day(frame: pd.DataFrame, signal_timestamp: datetime) -> pd.DataFrame:
    sliced = _slice_to_signal_time(frame, signal_timestamp)
    return sliced[sliced.index.date == signal_timestamp.astimezone(EASTERN).date()]


def _pct_change(value: float, base: float) -> float:
    if base == 0:
        return 0.0
    return ((value - base) / base) * 100


def _opening_range_break(last_close: float, high_15: float, low_15: float) -> str:
    if last_close > high_15:
        return "break_above"
    if last_close < low_15:
        return "break_below"
    return "inside_range"


def _gap_behavior(open_price: float, prior_close: float, last_close: float) -> str:
    if open_price >= prior_close and last_close >= open_price:
        return "holding"
    if open_price <= prior_close and last_close <= open_price:
        return "holding"
    if open_price >= prior_close and last_close < open_price:
        return "fading"
    if open_price <= prior_close and last_close > open_price:
        return "fading"
    return "mixed"


def _close_location(close_: float, high_: float, low_: float) -> float:
    width = max(high_ - low_, 1e-9)
    return (close_ - low_) / width


def _historical_intraday_averages(frame: pd.DataFrame) -> tuple[float, float, float]:
    if frame.empty:
        return 0.0, 1.0, 0.0
    grouped = []
    for _, day in frame.groupby(frame.index.date):
        if len(day) < 6:
            continue
        first_3 = day.iloc[:3]
        grouped.append(
            (
                _pct_change(float(first_3["close"].iloc[-1]), float(day["open"].iloc[0])),
                float(first_3["volume"].sum()),
                _pct_change(float(day["close"].iloc[-1]), float(first_3["close"].iloc[-1])),
            )
        )
    if not grouped:
        return 0.0, 1.0, 0.0
    returns, volumes, persistence = zip(*grouped[:-1] or grouped)
    return sum(returns) / len(returns), sum(volumes) / len(volumes), sum(persistence) / len(persistence)


def _average_true_range(daily: pd.DataFrame, window: int) -> float:
    subset = daily.tail(window + 1).copy()
    prev_close = subset["close"].shift(1)
    tr = pd.concat(
        [
            subset["high"] - subset["low"],
            (subset["high"] - prev_close).abs(),
            (subset["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.tail(window).mean())


def _benchmark_first_15m_return(day: pd.DataFrame) -> float:
    if len(day) < 3:
        return 0.0
    return _pct_change(float(day["close"].iloc[2]), float(day["open"].iloc[0]))


def _benchmark_gap(frame: pd.DataFrame, signal_timestamp: datetime) -> float:
    if frame.empty:
        return 0.0
    same_day = _select_day(frame, signal_timestamp)
    if same_day.empty:
        return 0.0
    prior = frame[frame.index.date < same_day.index[0].date()]
    if prior.empty:
        return 0.0
    return _pct_change(float(same_day["open"].iloc[0]), float(prior["close"].iloc[-1]))
