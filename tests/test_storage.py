from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opx.models import BatchRunResult, SignalResult, SignalRunRecord
from opx.storage.file_store import FileSignalStore


class FileStoreTests(unittest.TestCase):
    def test_round_trip_batch(self) -> None:
        run = SignalRunRecord(
            run_id="run-1",
            run_timestamp=datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
            signal_time_et="09:45",
            provider_name="yfinance",
            engine_version="0.1.0",
            config_version="2",
            tickers=["NVDA"],
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
        self.assertEqual(loaded[0].signals[0].ticker, "NVDA")


if __name__ == "__main__":
    unittest.main()
