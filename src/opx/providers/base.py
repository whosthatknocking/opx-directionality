from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from opx.models import NormalizedMarketData


class DataUnavailableError(RuntimeError):
    pass


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def fetch_intraday(self, ticker: str, now: datetime) -> NormalizedMarketData:
        raise NotImplementedError

    @abstractmethod
    def fetch_daily(self, ticker: str) -> NormalizedMarketData:
        raise NotImplementedError
