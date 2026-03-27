from __future__ import annotations

from opx.config import EngineConfig
from opx.providers.base import MarketDataProvider
from opx.providers.yfinance import YFinanceProvider


def create_provider(config: EngineConfig) -> MarketDataProvider:
    if config.provider.name == "yfinance":
        return YFinanceProvider(
            intraday_days=config.lookback_days_intraday,
            daily_days=config.lookback_days_daily,
            interval=config.bar_interval,
        )
    raise ValueError(f"unsupported provider: {config.provider.name}")
