from datetime import datetime
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opx.features.compute import build_feature_set
from opx.models import NormalizedMarketData


EASTERN = ZoneInfo("America/New_York")


class FeatureCutoffTests(unittest.TestCase):
    def test_daily_context_ignores_in_progress_trade_date_bar(self) -> None:
        signal_time = datetime(2026, 3, 26, 9, 45, tzinfo=EASTERN)
        intraday = _intraday_dataset("NVDA", [100.0, 101.0, 102.0, 103.0])
        benchmark = _intraday_dataset("QQQ", [200.0, 200.5, 201.0, 201.5])
        daily = NormalizedMarketData(
            symbol="NVDA",
            timeframe="daily",
            provider="test",
            bars=pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(
                        [
                            "2026-03-18T16:00:00-04:00",
                            "2026-03-19T16:00:00-04:00",
                            "2026-03-20T16:00:00-04:00",
                            "2026-03-23T16:00:00-04:00",
                            "2026-03-24T16:00:00-04:00",
                            "2026-03-25T16:00:00-04:00",
                            "2026-03-26T16:00:00-04:00",
                        ]
                    ),
                    "open": [90, 92, 94, 96, 98, 100, 105],
                    "high": [91, 93, 95, 97, 99, 101, 130],
                    "low": [89, 91, 93, 95, 97, 99, 80],
                    "close": [90, 92, 94, 96, 98, 100, 120],
                    "volume": [1, 1, 1, 1, 1, 1, 1],
                }
            ),
        )

        features = build_feature_set(intraday, daily, {"QQQ": benchmark, "SPY": benchmark}, signal_time)

        self.assertEqual(features.previous_day_return, ((100 - 98) / 98) * 100)
        self.assertEqual(features.five_day_return, ((100 - 90) / 90) * 100)


def _intraday_dataset(symbol: str, closes: list[float]) -> NormalizedMarketData:
    timestamps = pd.to_datetime(
        [
            "2026-03-25T09:30:00-04:00",
            "2026-03-25T09:35:00-04:00",
            "2026-03-25T09:40:00-04:00",
            "2026-03-25T09:45:00-04:00",
            "2026-03-26T09:30:00-04:00",
            "2026-03-26T09:35:00-04:00",
            "2026-03-26T09:40:00-04:00",
            "2026-03-26T09:45:00-04:00",
        ]
    )
    values = [90.0, 91.0, 92.0, 93.0] + closes
    return NormalizedMarketData(
        symbol=symbol,
        timeframe="intraday",
        provider="test",
        bars=pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": values,
                "high": [value + 0.5 for value in values],
                "low": [value - 0.5 for value in values],
                "close": values,
                "volume": [100] * len(values),
            }
        ),
    )


if __name__ == "__main__":
    unittest.main()
