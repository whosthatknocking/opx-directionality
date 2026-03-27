from datetime import datetime
from zoneinfo import ZoneInfo
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opx.config import ScoringConfig
from opx.models import FeatureSet
from opx.signals.rule_engine import score_signal


class RuleEngineTests(unittest.TestCase):
    def test_bullish_signal_maps_to_trend_continuation(self) -> None:
        features = FeatureSet(
            gap_pct=1.2,
            first_5m_return=0.5,
            first_10m_return=0.8,
            first_15m_return=1.1,
            first_15m_range_pct=1.4,
            first_15m_close_vs_open=1.1,
            price_vs_vwap_pct=0.3,
            opening_volume_multiple=1.9,
            opening_range_break_status="break_above",
            gap_hold_or_fade="holding",
            candle_body_to_range_ratio=0.75,
            intraday_high_low_position=0.9,
            previous_day_return=0.4,
            previous_day_close_location_in_range=0.8,
            three_day_return=2.1,
            five_day_return=3.8,
            atr_normalized_recent_move=1.3,
            average_first_15m_return=0.25,
            average_first_15m_volume=1000000,
            average_trend_persistence=0.6,
            first_15m_return_minus_qqq=0.7,
            first_15m_return_minus_spy=0.6,
            gap_pct_minus_qqq_gap=0.3,
            gap_pct_minus_spy_gap=0.2,
        )
        signal = score_signal(
            "NVDA",
            datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
            features,
            ScoringConfig(),
        )

        self.assertEqual(signal.bias, "bullish")
        self.assertEqual(signal.regime, "trend_continuation")
        self.assertGreaterEqual(signal.confidence, 60)
        self.assertEqual(signal.option_posture, "bullish_premium_sale_favored")


if __name__ == "__main__":
    unittest.main()
