import tempfile
import textwrap
import unittest

from opx.config import load_config


class ConfigLoadTests(unittest.TestCase):
    def test_load_config_normalizes_tickers(self) -> None:
        with tempfile.NamedTemporaryFile("w+", suffix=".toml") as handle:
            handle.write(
                textwrap.dedent(
                    """
                    [settings]
                    tickers = ["nvda", "tsla"]
                    benchmark_primary = "qqq"
                    benchmark_secondary = "spy"
                    signal_time_et = "09:45"
                    bar_interval = "5m"
                    lookback_days_intraday = 20
                    lookback_days_daily = 10
                    engine_version = "0.1.0"
                    config_version = "2"
                    data_provider = "yfinance"
                    storage_type = "file"
                    logging_dir = "logs"
                    bullish_threshold = 3
                    bearish_threshold = -3
                    vwap_band_pct = 0.15
                    strong_move_pct = 0.75
                    relative_strength_pct = 0.30
                    volume_multiple_threshold = 1.5

                    [storage.file]
                    target = "output/runs"

                    [providers.yfinance]
                    interval = "5m"
                    """
                )
            )
            handle.flush()
            config = load_config(handle.name)

        self.assertEqual(config.tickers, ["NVDA", "TSLA"])
        self.assertEqual(config.benchmark_primary, "QQQ")
        self.assertEqual(config.provider.name, "yfinance")
        self.assertEqual(config.provider.selected_settings()["interval"], "5m")
        self.assertEqual(config.storage.target, "output/runs")
        self.assertEqual(config.scoring.bullish_threshold, 3)


if __name__ == "__main__":
    unittest.main()
