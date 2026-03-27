from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from opx.models import NormalizedMarketData
from opx.providers.base import DataUnavailableError, MarketDataProvider

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - handled by runtime
    yf = None


EASTERN = ZoneInfo("America/New_York")


@dataclass
class YFinanceProvider(MarketDataProvider):
    intraday_days: int
    daily_days: int
    interval: str = "5m"
    name: str = "yfinance"

    def _ensure_dependency(self) -> None:
        if yf is None:
            raise DataUnavailableError("yfinance is not installed")

    def fetch_intraday(self, ticker: str, now: datetime) -> NormalizedMarketData:
        self._ensure_dependency()
        period = f"{max(self.intraday_days, 5)}d"
        frame = yf.download(
            tickers=ticker,
            period=period,
            interval=self.interval,
            auto_adjust=False,
            progress=False,
            threads=False,
            prepost=False,
        )
        if frame.empty:
            raise DataUnavailableError(f"no intraday data for {ticker}")
        normalized = self._normalize_frame(frame)
        normalized = self._filter_session_hours(normalized, now)
        return NormalizedMarketData(symbol=ticker, timeframe="intraday", provider=self.name, bars=normalized)

    def fetch_daily(self, ticker: str) -> NormalizedMarketData:
        self._ensure_dependency()
        period = f"{max(self.daily_days + 10, 30)}d"
        frame = yf.download(
            tickers=ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if frame.empty:
            raise DataUnavailableError(f"no daily data for {ticker}")
        normalized = self._normalize_frame(frame)
        return NormalizedMarketData(symbol=ticker, timeframe="daily", provider=self.name, bars=normalized)

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        if isinstance(normalized.columns, pd.MultiIndex):
            normalized.columns = [column[0].lower() for column in normalized.columns]
        else:
            normalized.columns = [str(column).lower() for column in normalized.columns]
        index = pd.to_datetime(normalized.index)
        if index.tz is None:
            index = index.tz_localize("UTC").tz_convert(EASTERN)
        else:
            index = index.tz_convert(EASTERN)
        normalized = normalized.assign(timestamp=index)
        return normalized.loc[:, ["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

    def _filter_session_hours(self, frame: pd.DataFrame, now: datetime) -> pd.DataFrame:
        if frame.empty:
            return frame
        eastern_now = now.astimezone(EASTERN)
        timestamps = pd.to_datetime(frame["timestamp"])
        same_day = timestamps.dt.date <= eastern_now.date()
        filtered = frame[same_day].copy()
        ts = pd.to_datetime(filtered["timestamp"])
        session_open = ts.dt.normalize() + pd.Timedelta(hours=9, minutes=30)
        session_close = ts.dt.normalize() + pd.Timedelta(hours=16)
        return filtered[(ts >= session_open) & (ts <= session_close)].reset_index(drop=True)
