from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo
import unittest

from opx.models import BatchRunResult, SignalResult, SignalRunRecord
from opx.storage.file_store import FileSignalStore


class FileStoreTests(unittest.TestCase):
    def test_round_trip_batch(self) -> None:
        run = SignalRunRecord(
            run_id="run-1",
            run_timestamp=datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
            trade_date="2026-03-26",
            signal_time_et="09:45",
            provider_name="yfinance",
            engine_version="0.1.0",
            config_version="2",
            config_fingerprint="cfg-1",
            tickers=["NVDA"],
            signal_time_reached=True,
            completion_rate=1.0,
            selection_status="canonical",
            selection_reason="earliest_complete_post_signal",
            log_path="logs/run-1.log",
        )
        signal = SignalResult(
            ticker="NVDA",
            signal_time=datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
            bias="bullish",
            confidence=75,
            regime="trend_continuation",
            option_posture="bullish_premium_sale_favored",
            raw_score=7,
            factors={"gap_pct": 1.2},
            factor_summary=[{"name": "gap_pct", "score": 2, "rationale": "gap is holding"}],
        )

        with TemporaryDirectory() as directory:
            store = FileSignalStore(Path(directory))
            store.save_batch(BatchRunResult(run=run, signals=[signal]))
            loaded = store.load_batches()

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].run.provider_name, "yfinance")
        self.assertEqual(loaded[0].run.selection_status, "canonical")
        self.assertEqual(loaded[0].signals[0].ticker, "NVDA")

    def test_later_complete_run_becomes_canonical(self) -> None:
        early = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-early",
                run_timestamp=datetime(2026, 3, 26, 9, 40, tzinfo=ZoneInfo("America/New_York")),
                trade_date="2026-03-26",
                signal_time_et="09:45",
                provider_name="yfinance",
                engine_version="0.1.0",
                config_version="2",
                config_fingerprint="cfg-1",
                tickers=["NVDA"],
                signal_time_reached=False,
                completion_rate=0.0,
                validation_state="partial",
                selection_status="diagnostic",
                selection_reason="ran_before_signal_time",
            ),
            signals=[
                SignalResult(
                    ticker="NVDA",
                    signal_time=datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
                    bias="neutral",
                    confidence=0,
                    regime="choppy",
                    option_posture="unavailable",
                    raw_score=0,
                    factors={},
                    factor_summary=[],
                    status="unavailable",
                    reason="not enough bars",
                    validation_state="invalid",
                )
            ],
        )
        complete = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-complete",
                run_timestamp=datetime(2026, 3, 26, 9, 46, tzinfo=ZoneInfo("America/New_York")),
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
            ),
            signals=[
                SignalResult(
                    ticker="NVDA",
                    signal_time=datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
                    bias="bullish",
                    confidence=72,
                    regime="trend_continuation",
                    option_posture="bullish_premium_sale_favored",
                    raw_score=7,
                    factors={"gap_pct": 1.2},
                    factor_summary=[{"name": "gap_pct", "score": 2, "rationale": "gap is holding"}],
                )
            ],
        )

        with TemporaryDirectory() as directory:
            store = FileSignalStore(Path(directory))
            store.save_batch(early)
            store.save_batch(complete)
            loaded = {batch.run.run_id: batch for batch in store.load_batches()}

        self.assertEqual(loaded["run-early"].run.selection_status, "diagnostic")
        self.assertEqual(loaded["run-complete"].run.selection_status, "canonical")


if __name__ == "__main__":
    unittest.main()
