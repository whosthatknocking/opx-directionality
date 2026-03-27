import tempfile
import textwrap
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opx.config import load_config


class ConfigLoadTests(unittest.TestCase):
    def test_load_config_normalizes_tickers(self) -> None:
        with tempfile.NamedTemporaryFile("w+", suffix=".toml") as handle:
            handle.write(
                textwrap.dedent(
                    """
                    tickers = ["nvda", "tsla"]
                    benchmark_primary = "qqq"
                    benchmark_secondary = "spy"
                    signal_time_et = "09:45"
                    bar_interval = "5m"
                    lookback_days_intraday = 20
                    lookback_days_daily = 10
                    engine_version = "0.1.0"
                    config_version = "2"

                    [provider]
                    name = "yfinance"
                    """
                )
            )
            handle.flush()
            config = load_config(handle.name)

        self.assertEqual(config.tickers, ["NVDA", "TSLA"])
        self.assertEqual(config.benchmark_primary, "QQQ")
        self.assertEqual(config.provider.name, "yfinance")
        self.assertEqual(config.scoring.bullish_threshold, 3)


if __name__ == "__main__":
    unittest.main()
