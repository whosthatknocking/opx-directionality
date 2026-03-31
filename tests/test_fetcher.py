from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

from opx import fetcher
from opx.models import BatchRunResult, NormalizedMarketData, SignalResult, SignalRunRecord


EASTERN = ZoneInfo("America/New_York")


class FetcherTests(unittest.TestCase):
    def test_main_backfills_realized_returns_during_normal_persist_flow(self) -> None:
        prior_batch = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-prior",
                run_timestamp=datetime(2026, 3, 30, 9, 46, tzinfo=EASTERN),
                trade_date="2026-03-30",
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
                    signal_time=datetime(2026, 3, 30, 9, 45, tzinfo=EASTERN),
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
        current_batch = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-current",
                run_timestamp=datetime(2026, 3, 31, 9, 46, tzinfo=EASTERN),
                trade_date="2026-03-31",
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
                    signal_time=datetime(2026, 3, 31, 9, 45, tzinfo=EASTERN),
                    bias="bullish",
                    confidence=82,
                    regime="trend_continuation",
                    option_posture="bullish_premium_sale_favored",
                    raw_score=8,
                    factors={"gap_pct": 1.5},
                    factor_summary=[],
                    signal_price=101.0,
                )
            ],
        )
        store = _MemoryStore([prior_batch])
        config = SimpleNamespace(storage=SimpleNamespace(kind="file", target="unused"))

        with (
            patch.object(fetcher, "build_parser", return_value=_ParserStub()),
            patch.object(fetcher, "load_config", return_value=config),
            patch.object(fetcher, "run_daily_engine", return_value=current_batch),
            patch.object(fetcher, "render_console_report", return_value="report"),
            patch.object(fetcher, "create_signal_store", return_value=store),
            patch.object(
                fetcher,
                "create_provider",
                return_value=_StaticProvider(close_price=103.0),
            ),
            patch("builtins.print"),
        ):
            exit_code = fetcher.main()

        self.assertEqual(exit_code, 0)
        realized_signal = store.batches["run-prior"].signals[0]
        self.assertEqual(realized_signal.realized_close, 103.0)
        self.assertAlmostEqual(realized_signal.realized_return_pct, 3.0)
        self.assertEqual(realized_signal.realized_outcome, "positive")
        self.assertTrue(realized_signal.directional_hit)


class _ParserStub:
    def parse_args(self) -> Namespace:
        return Namespace(
            config="unused",
            storage_kind=None,
            storage_target=None,
            no_persist=False,
        )


class _MemoryStore:
    def __init__(self, batches: list[BatchRunResult]) -> None:
        self.batches = {batch.run.run_id: batch for batch in batches}

    def initialize(self) -> None:
        return None

    def save_batch(self, batch: BatchRunResult) -> None:
        self.batches[batch.run.run_id] = batch

    def load_batches(self, limit: int | None = None) -> list[BatchRunResult]:
        batches = sorted(self.batches.values(), key=lambda batch: batch.run.run_timestamp)
        if limit is None:
            return batches
        return batches[-limit:]


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
                            "2026-03-30T16:00:00-04:00",
                            "2026-03-31T16:00:00-04:00",
                        ]
                    ),
                    "open": [98.0, 101.0],
                    "high": [104.0, 105.0],
                    "low": [97.0, 100.0],
                    "close": [self.close_price, 104.0],
                    "volume": [2000, 2200],
                }
            ),
        )

    def fetch_intraday(self, ticker: str, now=None) -> NormalizedMarketData:
        _ = (ticker, now)
        raise AssertionError("fetch_intraday should not be used when signal_price is already set")


if __name__ == "__main__":
    unittest.main()
