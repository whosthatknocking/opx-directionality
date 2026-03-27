from datetime import datetime
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opx.viewer import render_html_report
from opx.models import BatchRunResult, SignalResult, SignalRunRecord


class ViewerReportTests(unittest.TestCase):
    def test_render_html_report_contains_summary_and_table_content(self) -> None:
        batch = BatchRunResult(
            run=SignalRunRecord(
                run_id="run-1",
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
                selection_status="canonical",
                selection_reason="earliest_complete_post_signal",
            ),
            signals=[
                SignalResult(
                    ticker="NVDA",
                    signal_time=datetime(2026, 3, 26, 9, 45, tzinfo=ZoneInfo("America/New_York")),
                    bias="bullish",
                    confidence=77,
                    regime="trend_continuation",
                    option_posture="bullish_premium_sale_favored",
                    raw_score=6,
                    factors={"gap_pct": 1.0},
                    factor_summary=[{"name": "gap_pct", "score": 2, "rationale": "gap is holding"}],
                )
            ],
        )

        html = render_html_report(
            frame=_frame_from_batch(batch),
            storage_kind="file",
            storage_target="output/runs",
        )

        self.assertIn("Directionality Viewer", html)
        self.assertIn("Options Screener", html)
        self.assertIn("NVDA", html)
        self.assertIn("output/runs", html)
        self.assertIn("canonical", html)
        self.assertNotIn("# Field Reference", html)
        self.assertIn("Normalized Market Bar Fields", html)
        self.assertIn("Validation Strategy", html)
        self.assertIn("header-filter-button", html)
        self.assertIn("header-sort-button", html)
        self.assertIn("filter-popover", html)


def _frame_from_batch(batch: BatchRunResult):
    import pandas as pd

    rows = []
    for signal in batch.signals:
        rows.append(
            {
                "run_id": batch.run.run_id,
                "run_timestamp": batch.run.run_timestamp.isoformat(),
                "trade_date": batch.run.trade_date,
                "provider_name": batch.run.provider_name,
                "selection_status": batch.run.selection_status,
                "run_validation_state": batch.run.validation_state,
                "completion_rate": batch.run.completion_rate,
                "ticker": signal.ticker,
                "status": signal.status,
                "bias": signal.bias,
                "confidence": signal.confidence,
                "regime": signal.regime,
                "raw_score": signal.raw_score,
                "signal_validation_state": signal.validation_state,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
