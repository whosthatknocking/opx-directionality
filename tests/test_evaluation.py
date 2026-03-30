from __future__ import annotations

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from opx.evaluation import evaluate_canonical_batches
from opx.models import BatchRunResult, NormalizedMarketData, SignalResult, SignalRunRecord


EASTERN = ZoneInfo("America/New_York")


class EvaluationTests(unittest.TestCase):
    def test_evaluate_canonical_batches_records_close_of_day_outcomes(self) -> None:
        batch = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-1",
                run_timestamp=datetime(2026, 3, 26, 9, 46, tzinfo=EASTERN),
                trade_date="2026-03-25",
                signal_time_et="09:45",
                provider_name="yfinance",
                engine_version="0.1.0",
                config_version="2",
                config_fingerprint="cfg-1",
                tickers=["NVDA"],
                signal_time_reached=True,
                completion_rate=1.0,
                validation_state="valid",
                selection_status="canonical",
                selection_reason="earliest_complete_post_signal",
            ),
            signals=[
                SignalResult(
                    ticker="NVDA",
                    signal_time=datetime(2026, 3, 25, 9, 45, tzinfo=EASTERN),
                    bias="bullish",
                    confidence=80,
                    regime="trend_continuation",
                    option_posture="bullish_premium_sale_favored",
                    raw_score=7,
                    factors={"gap_pct": 1.2},
                    factor_summary=[],
                    signal_price=100.0,
                )
            ],
        )

        updated = evaluate_canonical_batches(
            [batch],
            provider=_StaticProvider(close_price=103.0),
            now=datetime(2026, 3, 26, 12, 0, tzinfo=EASTERN),
        )

        signal = updated[0].signals[0]
        self.assertEqual(signal.realized_close, 103.0)
        self.assertAlmostEqual(signal.realized_return_pct, 3.0)
        self.assertEqual(signal.realized_outcome, "positive")
        self.assertTrue(signal.directional_hit)

    def test_evaluate_canonical_batches_matches_date_only_daily_bars(self) -> None:
        batch = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-1",
                run_timestamp=datetime(2026, 3, 27, 9, 46, tzinfo=EASTERN),
                trade_date="2026-03-26",
                signal_time_et="09:45",
                provider_name="yfinance",
                engine_version="0.1.0",
                config_version="2",
                config_fingerprint="cfg-1",
                tickers=["NVDA"],
                signal_time_reached=True,
                completion_rate=1.0,
                validation_state="valid",
                selection_status="canonical",
                selection_reason="earliest_complete_post_signal",
            ),
            signals=[
                SignalResult(
                    ticker="NVDA",
                    signal_time=datetime(2026, 3, 26, 9, 45, tzinfo=EASTERN),
                    bias="bullish",
                    confidence=80,
                    regime="trend_continuation",
                    option_posture="bullish_premium_sale_favored",
                    raw_score=7,
                    factors={"gap_pct": 1.2},
                    factor_summary=[],
                    signal_price=100.0,
                )
            ],
        )

        updated = evaluate_canonical_batches(
            [batch],
            provider=_DateOnlyProvider(close_price=103.0),
            now=datetime(2026, 3, 27, 12, 0, tzinfo=EASTERN),
        )

        signal = updated[0].signals[0]
        self.assertEqual(signal.realized_close, 103.0)
        self.assertAlmostEqual(signal.realized_return_pct, 3.0)
        self.assertEqual(signal.realized_outcome, "positive")
        self.assertTrue(signal.directional_hit)

    def test_evaluate_canonical_batches_backfills_missing_signal_price_from_intraday(self) -> None:
        batch = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-1",
                run_timestamp=datetime(2026, 3, 27, 9, 46, tzinfo=EASTERN),
                trade_date="2026-03-26",
                signal_time_et="09:45",
                provider_name="yfinance",
                engine_version="0.1.0",
                config_version="2",
                config_fingerprint="cfg-1",
                tickers=["NVDA"],
                signal_time_reached=True,
                completion_rate=1.0,
                validation_state="valid",
                selection_status="canonical",
                selection_reason="earliest_complete_post_signal",
            ),
            signals=[
                SignalResult(
                    ticker="NVDA",
                    signal_time=datetime(2026, 3, 26, 9, 45, tzinfo=EASTERN),
                    bias="bullish",
                    confidence=80,
                    regime="trend_continuation",
                    option_posture="bullish_premium_sale_favored",
                    raw_score=7,
                    factors={"gap_pct": 1.2},
                    factor_summary=[],
                    signal_price=None,
                )
            ],
        )

        updated = evaluate_canonical_batches(
            [batch],
            provider=_BackfillProvider(close_price=103.0, signal_price=100.0),
            now=datetime(2026, 3, 27, 12, 0, tzinfo=EASTERN),
        )

        signal = updated[0].signals[0]
        self.assertEqual(signal.signal_price, 100.0)
        self.assertEqual(signal.realized_close, 103.0)
        self.assertAlmostEqual(signal.realized_return_pct, 3.0)
        self.assertEqual(signal.realized_outcome, "positive")
        self.assertTrue(signal.directional_hit)


class _StaticProvider:
    name = "test"

    def __init__(self, close_price: float) -> None:
        self.close_price = close_price

    def fetch_daily(self, ticker: str, min_date=None) -> NormalizedMarketData:
        _ = min_date
        return NormalizedMarketData(
            symbol=ticker,
            timeframe="daily",
            provider="test",
            bars=pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(
                        [
                            "2026-03-24T16:00:00-04:00",
                            "2026-03-25T16:00:00-04:00",
                        ]
                    ),
                    "open": [98.0, 100.0],
                    "high": [99.0, 104.0],
                    "low": [97.0, 99.0],
                    "close": [99.0, self.close_price],
                    "volume": [1000, 2000],
                }
            ),
        )

    def fetch_intraday(self, ticker: str, now=None) -> NormalizedMarketData:
        _ = (ticker, now)
        raise AssertionError("fetch_intraday should not be used when signal_price is already set")


class _DateOnlyProvider:
    name = "test"

    def __init__(self, close_price: float) -> None:
        self.close_price = close_price

    def fetch_daily(self, ticker: str, min_date=None) -> NormalizedMarketData:
        _ = (ticker, min_date)
        return NormalizedMarketData(
            symbol="NVDA",
            timeframe="daily",
            provider="test",
            bars=pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(
                        [
                            "2026-03-25",
                            "2026-03-26",
                        ]
                    ),
                    "open": [98.0, 100.0],
                    "high": [99.0, 104.0],
                    "low": [97.0, 99.0],
                    "close": [99.0, self.close_price],
                    "volume": [1000, 2000],
                }
            ),
        )

    def fetch_intraday(self, ticker: str, now=None) -> NormalizedMarketData:
        _ = (ticker, now)
        raise AssertionError("fetch_intraday should not be used when signal_price is already set")


class _BackfillProvider:
    name = "test"

    def __init__(self, close_price: float, signal_price: float) -> None:
        self.close_price = close_price
        self.signal_price = signal_price

    def fetch_daily(self, ticker: str, min_date=None) -> NormalizedMarketData:
        _ = (ticker, min_date)
        return NormalizedMarketData(
            symbol="NVDA",
            timeframe="daily",
            provider="test",
            bars=pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(["2026-03-26T16:00:00-04:00"]),
                    "open": [98.0],
                    "high": [104.0],
                    "low": [97.0],
                    "close": [self.close_price],
                    "volume": [2000],
                }
            ),
        )

    def fetch_intraday(self, ticker: str, now=None) -> NormalizedMarketData:
        _ = (ticker, now)
        return NormalizedMarketData(
            symbol="NVDA",
            timeframe="intraday",
            provider="test",
            bars=pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(
                        [
                            "2026-03-26T09:40:00-04:00",
                            "2026-03-26T09:45:00-04:00",
                        ]
                    ),
                    "open": [99.0, 100.0],
                    "high": [100.0, 101.0],
                    "low": [98.0, 99.0],
                    "close": [99.5, self.signal_price],
                    "volume": [1000, 1200],
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()
