from __future__ import annotations

import argparse
import json
import re
import webbrowser
from pathlib import Path
from typing import Any

import pandas as pd

from opx.storage import create_signal_store


DEFAULT_VIEWER_OUTPUT = "output/viewer/index.html"
REPO_ROOT = Path(__file__).resolve().parents[2]
FIELD_REFERENCE_PATH = REPO_ROOT / "docs" / "FIELD_REFERENCE.md"
VALIDATION_PATH = REPO_ROOT / "docs" / "VALIDATION.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visualize and evaluate multiple opx-directionality runs.")
    parser.add_argument("--storage-kind", default="file", help="Storage backend to read from.")
    parser.add_argument("--storage-target", default="output/runs", help="Storage location to read from.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of historical runs to load.")
    parser.add_argument("--output", default=DEFAULT_VIEWER_OUTPUT, help="Path to the generated HTML report.")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML report in the default browser.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    store = create_signal_store(args.storage_kind, args.storage_target)
    batches = store.load_batches(limit=args.limit)
    if not batches:
        print("no persisted runs found")
        return 1

    frame = _flatten_batches(batches)
    report_path = Path(args.output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_html_report(frame, args.storage_kind, args.storage_target),
        encoding="utf-8",
    )
    if args.open:
        webbrowser.open(report_path.resolve().as_uri())
    _print_summary(frame, report_path)
    return 0


def _flatten_batches(batches) -> pd.DataFrame:
    rows = []
    for batch in batches:
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
    return pd.DataFrame(rows).sort_values(["ticker", "run_timestamp"])


def _print_summary(frame: pd.DataFrame, report_path: Path) -> None:
    available = frame[frame["status"] == "ok"]
    print(f"runs={frame['run_id'].nunique()} tickers={frame['ticker'].nunique()} signals={len(frame)}")
    canonical = frame[frame["selection_status"].isin(["canonical", "partial_canonical"])]
    if not canonical.empty:
        print(
            "canonical_runs="
            f"{canonical['run_id'].nunique()} partial_canonical_runs="
            f"{canonical[canonical['selection_status'] == 'partial_canonical']['run_id'].nunique()}"
        )
    if not available.empty:
        grouped = available.groupby("ticker").agg(
            avg_confidence=("confidence", "mean"),
            avg_raw_score=("raw_score", "mean"),
            bullish_rate=("bias", lambda values: (values == "bullish").mean()),
            bearish_rate=("bias", lambda values: (values == "bearish").mean()),
        )
        print(grouped.round(2).to_string())
    print(f"viewer_report={report_path}")


def render_html_report(frame: pd.DataFrame, storage_kind: str, storage_target: str) -> str:
    available = frame[frame["status"] == "ok"].copy()
    summary_rows = []
    if not available.empty:
        grouped = available.groupby("ticker").agg(
            runs=("run_id", "nunique"),
            avg_confidence=("confidence", "mean"),
            avg_raw_score=("raw_score", "mean"),
            bullish_rate=("bias", lambda values: float((values == "bullish").mean())),
            bearish_rate=("bias", lambda values: float((values == "bearish").mean())),
        )
        for _, row in grouped.reset_index().iterrows():
            summary_rows.append(
                {
                    "ticker": row["ticker"],
                    "runs": int(row["runs"]),
                    "avg_confidence": round(float(row["avg_confidence"]), 2),
                    "avg_raw_score": round(float(row["avg_raw_score"]), 2),
                    "bullish_rate": round(float(row["bullish_rate"]), 2),
                    "bearish_rate": round(float(row["bearish_rate"]), 2),
                }
            )

    status_rows = []
    for run_timestamp, group in frame.groupby("run_timestamp"):
        counts = group["status"].value_counts().to_dict()
        status_rows.append(
            {
                "run_timestamp": run_timestamp,
                "ok": int(counts.get("ok", 0)),
                "unavailable": int(counts.get("unavailable", 0)),
            }
        )

    payload = {
        "summary": {
            "run_count": int(frame["run_id"].nunique()),
            "ticker_count": int(frame["ticker"].nunique()),
            "signal_count": int(len(frame)),
            "canonical_count": int(
                frame[frame["selection_status"].isin(["canonical", "partial_canonical"])]["run_id"].nunique()
            ),
            "storage_kind": storage_kind,
            "storage_target": storage_target,
        },
        "summary_rows": summary_rows,
        "signals": [_normalize_record(record) for record in frame.to_dict(orient="records")],
        "status_rows": status_rows,
        "field_reference_html": _render_markdown(_load_markdown(FIELD_REFERENCE_PATH)),
        "validation_html": _render_markdown(_load_markdown(VALIDATION_PATH)),
        "column_descriptions": _column_descriptions(),
    }
    return _html_document(json.dumps(payload))


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in record.items():
        if pd.isna(value):
            normalized[key] = None
        elif hasattr(value, "item"):
            normalized[key] = value.item()
        else:
            normalized[key] = value
    return normalized


def _load_markdown(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _render_markdown(markdown: str) -> str:
    if not markdown.strip():
        return "<p>No documentation available.</p>"

    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    parts: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(paragraph).strip()
            if text:
                parts.append(f"<p>{_render_inline(text)}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            parts.append(f"</{list_type}>")
            list_type = None

    def flush_code() -> None:
        nonlocal code_lines, in_code
        if in_code:
            parts.append(f"<pre>{_escape_html(chr(10).join(code_lines))}</pre>")
            code_lines = []
            in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                flush_code()
            else:
                in_code = True
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            parts.append(f"<h{level}>{_render_inline(heading.group(2))}</h{level}>")
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet:
            flush_paragraph()
            if list_type != "ul":
                close_list()
                list_type = "ul"
                parts.append("<ul>")
            parts.append(f"<li>{_render_inline(bullet.group(1))}</li>")
            continue

        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered:
            flush_paragraph()
            if list_type != "ol":
                close_list()
                list_type = "ol"
                parts.append("<ol>")
            parts.append(f"<li>{_render_inline(ordered.group(1))}</li>")
            continue

        close_list()
        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    flush_code()
    return "".join(parts)


def _render_inline(text: str) -> str:
    escaped = _escape_html(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _column_descriptions() -> dict[str, str]:
    return {
        "run_timestamp": "Timestamp when the engine run started.",
        "trade_date": "Trade date associated with the configured signal timestamp.",
        "provider_name": "Data provider used for the run.",
        "selection_status": "Canonical-selection classification for the run.",
        "run_validation_state": "Validation result for the overall run.",
        "completion_rate": "Fraction of configured tickers that completed with status ok.",
        "ticker": "Evaluated symbol.",
        "status": "Signal availability state for the ticker.",
        "bias": "Directional lean produced by the rule engine.",
        "confidence": "Confidence score from 0 to 100.",
        "regime": "Market-condition classification for the signal.",
        "raw_score": "Summed rule score before bias and confidence mapping.",
        "signal_validation_state": "Validation result for the ticker-level signal.",
    }


def _html_document(payload_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Directionality Viewer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      color-scheme: light;
      --surface-primary: #ffffff;
      --surface-secondary: #f8fafc;
      --page-ground: #f8fafc;
      --text-primary: #0f172a;
      --text-secondary: #475569;
      --border: #e2e8f0;
      --positive: #10b981;
      --negative: #ef4444;
      --neutral: #3b82f6;
      --radius: 4px;
    }}
    :root[data-theme="dark"] {{
      color-scheme: dark;
      --surface-primary: #1e293b;
      --surface-secondary: #0f172a;
      --page-ground: #0f172a;
      --text-primary: #f1f5f9;
      --text-secondary: #94a3b8;
      --border: #334155;
      --positive: #10b981;
      --negative: #ef4444;
      --neutral: #3b82f6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Manrope", sans-serif;
      background: var(--page-ground);
      color: var(--text-primary);
    }}
    .page {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 16px;
      display: grid;
      gap: 12px;
    }}
    .surface {{
      background: var(--surface-primary);
      border: 1px solid var(--border);
      border-radius: var(--radius);
    }}
    .workspace-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
    }}
    .workspace-title p {{
      margin: 0 0 4px;
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .workspace-title h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1;
    }}
    .workspace-subtitle {{
      margin: 4px 0 0;
      color: var(--text-secondary);
      font-size: 13px;
    }}
    .workspace-controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .tabs {{
      display: inline-flex;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      background: var(--surface-secondary);
    }}
    .tab-button, .theme-toggle {{
      border: 0;
      background: transparent;
      color: var(--text-secondary);
      min-height: 34px;
      padding: 0 12px;
      font: inherit;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      cursor: pointer;
    }}
    .tab-button.active {{
      background: var(--surface-primary);
      color: var(--text-primary);
    }}
    .theme-toggle {{
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface-secondary);
    }}
    .panel {{
      padding: 12px;
    }}
    .panel-title {{
      margin: 0 0 4px;
      font-size: 15px;
      font-weight: 800;
    }}
    .panel-note {{
      margin: 0 0 12px;
      color: var(--text-secondary);
      font-size: 12px;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 8px;
    }}
    .stat-card {{
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface-secondary);
    }}
    .stat-label {{
      display: block;
      margin-bottom: 8px;
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    .stat-value {{
      font-size: 24px;
      font-weight: 800;
    }}
    .overview-grid {{
      display: grid;
      grid-template-columns: 1.1fr 1fr;
      gap: 12px;
    }}
    .chart-card {{
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface-primary);
    }}
    svg {{
      display: block;
      width: 100%;
      height: auto;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
      color: var(--text-secondary);
      font-size: 12px;
    }}
    .legend-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }}
    .table-scroll {{
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: var(--radius);
    }}
    .dataset-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }}
    .dataset-summary {{
      color: var(--text-secondary);
      font-size: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--surface-primary);
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      white-space: nowrap;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: var(--surface-secondary);
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      vertical-align: bottom;
    }}
    .header-label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: help;
      border-bottom: 1px dotted var(--text-secondary);
    }}
    .header-cell {{
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 8px;
    }}
    .header-sort-button {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 0;
      margin: 0;
      border: 0;
      background: transparent;
      color: inherit;
      font: inherit;
      text-transform: inherit;
      letter-spacing: inherit;
      cursor: pointer;
    }}
    .header-sort-indicator {{
      color: var(--neutral);
      font-size: 10px;
      font-weight: 800;
    }}
    .header-filter-button {{
      position: relative;
      width: 20px;
      height: 20px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: color-mix(in srgb, var(--surface-primary) 90%, var(--surface-secondary));
      color: var(--text-secondary);
      cursor: pointer;
      padding: 0;
      flex: 0 0 auto;
    }}
    .header-filter-button.active {{
      color: var(--neutral);
      border-color: var(--neutral);
    }}
    .header-filter-icon {{
      display: inline-flex;
      width: 100%;
      height: 100%;
      align-items: center;
      justify-content: center;
    }}
    .header-filter-icon svg {{
      width: 10px;
      height: 10px;
      fill: currentColor;
    }}
    .header-filter-count {{
      position: absolute;
      top: -5px;
      right: -5px;
      min-width: 14px;
      height: 14px;
      padding: 0 3px;
      border-radius: 999px;
      background: var(--neutral);
      color: #fff;
      font-size: 10px;
      font-weight: 800;
      line-height: 14px;
      text-align: center;
    }}
    .filter-popover {{
      position: absolute;
      z-index: 20;
      width: 280px;
      max-height: 340px;
      overflow: auto;
      padding: 10px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface-primary);
      color: var(--text-primary);
      display: none;
    }}
    .filter-popover.open {{
      display: block;
    }}
    .filter-popover-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .filter-popover-header strong {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--text-secondary);
    }}
    .filter-clear-button {{
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface-secondary);
      color: var(--text-primary);
      min-height: 28px;
      padding: 0 8px;
      font: inherit;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
    }}
    .filter-range-wrap {{
      display: grid;
      gap: 6px;
      margin-bottom: 10px;
    }}
    .filter-range-field span {{
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .filter-range-wrap {{
      grid-template-columns: 1fr 1fr;
    }}
    .filter-range-field {{
      display: grid;
      gap: 4px;
    }}
    .filter-range-field input {{
      min-height: 32px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 0 8px;
      background: var(--surface-secondary);
      color: var(--text-primary);
      font: inherit;
      font-size: 12px;
    }}
    .filter-option-list {{
      display: grid;
      gap: 6px;
    }}
    .filter-option {{
      display: flex;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      justify-content: space-between;
    }}
    .filter-option-label {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      flex: 1 1 auto;
      min-width: 0;
    }}
    .filter-option-value {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .filter-option-count {{
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 700;
    }}
    .filter-option-empty {{
      color: var(--text-secondary);
      font-size: 12px;
    }}
    .pill {{
      display: inline-flex;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .pill.ok, .pill.valid, .pill.canonical {{
      background: color-mix(in srgb, var(--positive) 12%, transparent);
      color: var(--positive);
    }}
    .pill.partial, .pill.partial_canonical {{
      background: color-mix(in srgb, var(--neutral) 12%, transparent);
      color: var(--neutral);
    }}
    .pill.unavailable, .pill.invalid {{
      background: color-mix(in srgb, var(--negative) 12%, transparent);
      color: var(--negative);
    }}
    .pill.retry, .pill.candidate, .pill.diagnostic {{
      background: color-mix(in srgb, var(--text-secondary) 12%, transparent);
      color: var(--text-secondary);
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .reference-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .reference-card {{
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 12px;
      background: var(--surface-secondary);
      min-height: 220px;
    }}
    .reference-body {{
      color: var(--text-primary);
      font-size: 13px;
      line-height: 1.6;
    }}
    .reference-body h1,
    .reference-body h2,
    .reference-body h3 {{
      margin: 16px 0 8px;
      font-size: 14px;
      font-weight: 800;
    }}
    .reference-body h1:first-child,
    .reference-body h2:first-child,
    .reference-body h3:first-child {{
      margin-top: 0;
    }}
    .reference-body p {{
      margin: 8px 0;
    }}
    .reference-body ul,
    .reference-body ol {{
      margin: 8px 0;
      padding-left: 20px;
    }}
    .reference-body li {{
      margin: 4px 0;
    }}
    .reference-body code {{
      font-family: "IBM Plex Mono", monospace;
      font-size: 12px;
      background: var(--surface-primary);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1px 4px;
    }}
    .reference-body pre {{
      margin: 10px 0;
      padding: 10px;
      overflow: auto;
      background: var(--surface-primary);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      font-family: "IBM Plex Mono", monospace;
      font-size: 12px;
      line-height: 1.5;
    }}
    @media (max-width: 1000px) {{
      .overview-grid, .reference-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="surface workspace-header">
      <div class="workspace-title">
        <p>Directionality Viewer</p>
        <h1>Options Screener</h1>
        <p class="workspace-subtitle">Persistent run analysis with canonical-run tracking, validation state, and repeat-run stability.</p>
      </div>
      <div class="workspace-controls">
        <nav class="tabs" aria-label="Primary">
          <button class="tab-button active" type="button" data-tab="overview">Overview</button>
          <button class="tab-button" type="button" data-tab="dataset">Dataset</button>
          <button class="tab-button" type="button" data-tab="reference">Reference</button>
        </nav>
        <button id="themeToggle" class="theme-toggle" type="button">Dark</button>
      </div>
    </header>

    <section class="surface panel">
      <div class="stat-grid" id="summaryCards"></div>
    </section>

    <section id="overviewTab" class="surface panel tab-panel active">
      <h2 class="panel-title">Overview</h2>
      <p class="panel-note">Institutional, ledger-style review of run quality, score movement, confidence, and signal availability.</p>
      <div class="overview-grid">
        <article class="chart-card">
          <h3 class="panel-title">Raw Score By Run</h3>
          <p class="panel-note">Per-ticker score movement across stored runs.</p>
          <div id="rawScoreChart"></div>
        </article>
        <article class="chart-card">
          <h3 class="panel-title">Confidence By Run</h3>
          <p class="panel-note">Per-ticker confidence trend across repeated runs.</p>
          <div id="confidenceChart"></div>
        </article>
      </div>
      <div class="overview-grid" style="margin-top:12px;">
        <article class="chart-card">
          <h3 class="panel-title">Availability By Run</h3>
          <p class="panel-note">Stacked bars for successful versus unavailable signals.</p>
          <div id="availabilityChart"></div>
          <div class="legend">
            <span class="legend-chip"><span class="legend-dot" style="background: var(--positive);"></span>ok</span>
            <span class="legend-chip"><span class="legend-dot" style="background: var(--negative);"></span>unavailable</span>
          </div>
        </article>
        <article class="chart-card">
          <h3 class="panel-title">Ticker Summary</h3>
          <p class="panel-note">Average score, confidence, and directional rates for successful signals.</p>
          <div class="table-scroll">
            <table id="summaryTable"></table>
          </div>
        </article>
      </div>
    </section>

    <section id="datasetTab" class="surface panel tab-panel">
      <h2 class="panel-title">Dataset</h2>
      <p class="panel-note">Flattened stored signal ledger used for the current viewer report.</p>
      <div class="dataset-toolbar">
        <div id="filterSummary" class="dataset-summary">Showing all rows.</div>
      </div>
      <div class="table-scroll">
        <table id="signalsTable"></table>
      </div>
    </section>

    <section id="referenceTab" class="surface panel tab-panel">
      <h2 class="panel-title">Reference</h2>
      <p class="panel-note">Local documentation snapshot bundled into the viewer report.</p>
      <div class="reference-grid">
        <article class="reference-card">
          <h3 class="panel-title">Field Reference</h3>
          <div id="fieldReference" class="reference-body"></div>
        </article>
        <article class="reference-card">
          <h3 class="panel-title">Validation Strategy</h3>
          <div id="validationReference" class="reference-body"></div>
        </article>
      </div>
    </section>
  </div>
  <div id="filterPopover" class="filter-popover" aria-hidden="true">
    <div class="filter-popover-header">
      <strong id="filterPopoverTitle">Filter</strong>
      <button id="clearFilterButton" class="filter-clear-button" type="button">Clear</button>
    </div>
    <div id="filterRangeWrap" class="filter-range-wrap" hidden>
      <label class="filter-range-field">
        <span>Min</span>
        <input id="filterMinValue" type="number" placeholder="Min">
      </label>
      <label class="filter-range-field">
        <span>Max</span>
        <input id="filterMaxValue" type="number" placeholder="Max">
      </label>
    </div>
    <div id="filterOptionList" class="filter-option-list"></div>
  </div>
  <script>
    const payload = {payload_json};
    const palette = ["#10b981", "#3b82f6", "#ef4444", "#8b5cf6", "#f59e0b", "#06b6d4", "#f97316", "#22c55e"];
    const state = {{
      columnFilters: {{}},
      activeFilterColumn: null,
      sortColumn: "run_timestamp",
      sortDirection: "desc",
    }};
    const DATASET_COLUMNS = [
      {{ key: "run_timestamp", label: "Run Timestamp", numeric: false }},
      {{ key: "ticker", label: "Ticker", numeric: false }},
      {{ key: "status", label: "Status", numeric: false }},
      {{ key: "bias", label: "Bias", numeric: false }},
      {{ key: "confidence", label: "Confidence", numeric: true }},
      {{ key: "raw_score", label: "Raw Score", numeric: true }},
      {{ key: "regime", label: "Regime", numeric: false }},
      {{ key: "selection_status", label: "Selection", numeric: false }},
      {{ key: "run_validation_state", label: "Run Validation", numeric: false }},
      {{ key: "signal_validation_state", label: "Signal Validation", numeric: false }},
    ];

    function fmt(value) {{
      if (value === null || value === undefined || value === "") return "—";
      if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
      return String(value);
    }}

    function fmtColumnValue(columnKey, value) {{
      if (columnKey === "run_timestamp" && value) {{
        const text = String(value);
        return text.replace(/\\.\\d+(?=(?:[+-]\\d\\d:\\d\\d|Z)?$)/, "");
      }}
      return fmt(value);
    }}

    function pillClass(value) {{
      const normalized = String(value || "").toLowerCase();
      if (["ok", "valid", "canonical"].includes(normalized)) return "pill ok";
      if (["partial", "partial_canonical"].includes(normalized)) return "pill partial";
      if (["unavailable", "invalid"].includes(normalized)) return "pill unavailable";
      return "pill retry";
    }}

    function renderCards() {{
      const summary = payload.summary;
      const cards = [
        ["Runs", summary.run_count],
        ["Tickers", summary.ticker_count],
        ["Signals", summary.signal_count],
        ["Canonical Runs", summary.canonical_count],
        ["Storage", `${{summary.storage_kind}} → ${{summary.storage_target}}`],
      ];
      document.getElementById("summaryCards").innerHTML = cards.map(([label, value]) => `
        <article class="stat-card">
          <span class="stat-label">${{label}}</span>
          <strong class="stat-value">${{value}}</strong>
        </article>
      `).join("");
    }}

    function headerLabel(column) {{
      const description = payload.column_descriptions[column.key] || column.label;
      return `<span class="header-label" title="${{description}}">${{column.label}}</span>`;
    }}

    function renderTable(elementId, rows, columns, pillColumns = []) {{
      const table = document.getElementById(elementId);
      const head = `<thead><tr>${{columns.map((column) => `<th title="${{payload.column_descriptions[column.key] || column.label}}">${{headerLabel(column)}}</th>`).join("")}}</tr></thead>`;
      const body = `<tbody>${{rows.map((row) => `<tr>${{columns.map((column) => {{
        const value = row[column.key];
        if (pillColumns.includes(column.key)) return `<td><span class="${{pillClass(value)}}">${{fmtColumnValue(column.key, value)}}</span></td>`;
        return `<td>${{fmtColumnValue(column.key, value)}}</td>`;
      }}).join("")}}</tr>`).join("")}}</tbody>`;
      table.innerHTML = head + body;
    }}

    function compareValues(left, right) {{
      const leftNumber = Number(left);
      const rightNumber = Number(right);
      if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber;
      return String(left ?? "").localeCompare(String(right ?? ""), undefined, {{ numeric: true, sensitivity: "base" }});
    }}

    function normalizeFilterValue(value) {{
      return value === null || value === undefined || value === "" ? "—" : String(value);
    }}

    function parseFilterNumber(value) {{
      if (value === "" || value === null || value === undefined) return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }}

    function getColumnDefinition(columnKey) {{
      return DATASET_COLUMNS.find((column) => column.key === columnKey) || null;
    }}

    function isRangeFilter(columnKey) {{
      return getColumnDefinition(columnKey)?.numeric === true;
    }}

    function hasActiveColumnFilter(columnKey) {{
      const filter = state.columnFilters[columnKey];
      if (!filter) return false;
      if (filter.type === "range") return filter.min !== null || filter.max !== null;
      return filter.values.size > 0;
    }}

    function getColumnFilterValues(columnKey) {{
      const counts = new Map();
      payload.signals.forEach((row) => {{
        const value = normalizeFilterValue(row[columnKey]);
        counts.set(value, (counts.get(value) || 0) + 1);
      }});
      return [...counts.entries()]
        .sort((left, right) => compareValues(left[0], right[0]))
        .map(([value, count]) => ({{ value, count }}));
    }}

    function getFilteredSignals() {{
      let rows = payload.signals.slice();
      Object.entries(state.columnFilters).forEach(([columnKey, filter]) => {{
        if (filter.type === "range") {{
          if (filter.min !== null || filter.max !== null) {{
            rows = rows.filter((row) => {{
              const value = Number(row[columnKey]);
              if (!Number.isFinite(value)) return false;
              if (filter.min !== null && value < filter.min) return false;
              if (filter.max !== null && value > filter.max) return false;
              return true;
            }});
          }}
          return;
        }}
        if (filter.values.size > 0) {{
          rows = rows.filter((row) => filter.values.has(normalizeFilterValue(row[columnKey])));
        }}
      }});
      if (state.sortColumn) {{
        rows.sort((left, right) => {{
          const delta = compareValues(left[state.sortColumn], right[state.sortColumn]);
          return state.sortDirection === "asc" ? delta : -delta;
        }});
      }}
      return rows;
    }}

    function closeFilterPopover() {{
      state.activeFilterColumn = null;
      const popover = document.getElementById("filterPopover");
      popover.classList.remove("open");
      popover.setAttribute("aria-hidden", "true");
    }}

    function updateFilterPopoverMode(columnKey) {{
      const numeric = isRangeFilter(columnKey);
      const rangeWrap = document.getElementById("filterRangeWrap");
      rangeWrap.hidden = !numeric;
      rangeWrap.style.display = numeric ? "grid" : "none";
      if (!numeric) {{
        document.getElementById("filterMinValue").value = "";
        document.getElementById("filterMaxValue").value = "";
      }}
    }}

    function renderFilterOptions() {{
      if (!state.activeFilterColumn || isRangeFilter(state.activeFilterColumn)) {{
        document.getElementById("filterOptionList").innerHTML = "";
        return;
      }}
      const activeFilter = state.columnFilters[state.activeFilterColumn];
      const selectedValues = activeFilter?.type === "set" ? activeFilter.values : new Set();
      const values = getColumnFilterValues(state.activeFilterColumn);
      const list = document.getElementById("filterOptionList");
      list.innerHTML = "";
      if (!values.length) {{
        list.innerHTML = '<div class="filter-option-empty">No matching values</div>';
        return;
      }}
      values.forEach((entry) => {{
        const label = document.createElement("label");
        label.className = "filter-option";
        const inner = document.createElement("span");
        inner.className = "filter-option-label";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = selectedValues.has(entry.value);
        checkbox.addEventListener("change", () => {{
          if (!state.columnFilters[state.activeFilterColumn] || state.columnFilters[state.activeFilterColumn].type !== "set") {{
            state.columnFilters[state.activeFilterColumn] = {{ type: "set", values: new Set() }};
          }}
          if (checkbox.checked) {{
            state.columnFilters[state.activeFilterColumn].values.add(entry.value);
          }} else {{
            state.columnFilters[state.activeFilterColumn].values.delete(entry.value);
            if (state.columnFilters[state.activeFilterColumn].values.size === 0) delete state.columnFilters[state.activeFilterColumn];
          }}
          renderDatasetTable();
          renderFilterOptions();
        }});
        const text = document.createElement("span");
        text.className = "filter-option-value";
        text.textContent = entry.value;
        const count = document.createElement("span");
        count.className = "filter-option-count";
        count.textContent = String(entry.count);
        inner.appendChild(checkbox);
        inner.appendChild(text);
        label.appendChild(inner);
        label.appendChild(count);
        list.appendChild(label);
      }});
    }}

    function openFilterPopover(columnKey, anchor) {{
      state.activeFilterColumn = columnKey;
      document.getElementById("filterPopoverTitle").textContent = `${{getColumnDefinition(columnKey)?.label || columnKey}} Filter`;
      updateFilterPopoverMode(columnKey);
      if (isRangeFilter(columnKey)) {{
        const filter = state.columnFilters[columnKey];
        document.getElementById("filterMinValue").value = filter?.type === "range" && filter.min !== null ? String(filter.min) : "";
        document.getElementById("filterMaxValue").value = filter?.type === "range" && filter.max !== null ? String(filter.max) : "";
      }}
      renderFilterOptions();
      const rect = anchor.getBoundingClientRect();
      const popover = document.getElementById("filterPopover");
      popover.style.top = `${{window.scrollY + rect.bottom + 6}}px`;
      popover.style.left = `${{Math.max(8, window.scrollX + rect.left - 180 + rect.width)}}px`;
      popover.classList.add("open");
      popover.setAttribute("aria-hidden", "false");
    }}

    function renderDatasetTable() {{
      const filtered = getFilteredSignals();
      const table = document.getElementById("signalsTable");
      const head = `<thead><tr>${{DATASET_COLUMNS.map((column) => {{
        const active = hasActiveColumnFilter(column.key);
        const filter = state.columnFilters[column.key];
        const count = active ? (column.numeric ? "R" : String(filter.values.size)) : "";
        const sortMark = state.sortColumn === column.key ? (state.sortDirection === "asc" ? "▲" : "▼") : "";
        return `<th title="${{payload.column_descriptions[column.key] || column.label}}">
          <div class="header-cell">
            <button class="header-sort-button" type="button" data-sort-column="${{column.key}}" aria-label="Sort by ${{column.label}}">
              ${{headerLabel(column)}}
              <span class="header-sort-indicator">${{sortMark}}</span>
            </button>
            <button class="header-filter-button ${{active ? "active" : ""}}" type="button" data-filter-column="${{column.key}}" aria-label="Filter ${{column.label}}">
              <span class="header-filter-icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" focusable="false"><path d="M2.5 3.5h11l-4.25 4.75v3.1l-2.5 1.45V8.25z"></path></svg>
              </span>
              ${{active ? `<span class="header-filter-count">${{count}}</span>` : ""}}
            </button>
          </div>
        </th>`;
      }}).join("")}}</tr></thead>`;
      const body = `<tbody>${{filtered.map((row) => `<tr>${{DATASET_COLUMNS.map((column) => {{
        const value = row[column.key];
        if (["status", "selection_status", "run_validation_state", "signal_validation_state"].includes(column.key)) {{
          return `<td><span class="${{pillClass(value)}}">${{fmtColumnValue(column.key, value)}}</span></td>`;
        }}
        return `<td>${{fmtColumnValue(column.key, value)}}</td>`;
      }}).join("")}}</tr>`).join("")}}</tbody>`;
      table.innerHTML = head + body;
      table.querySelectorAll("[data-sort-column]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const columnKey = button.dataset.sortColumn;
          if (state.sortColumn === columnKey) {{
            state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
          }} else {{
            state.sortColumn = columnKey;
            state.sortDirection = columnKey === "run_timestamp" ? "desc" : "asc";
          }}
          renderDatasetTable();
        }});
      }});
      table.querySelectorAll("[data-filter-column]").forEach((button) => {{
        button.addEventListener("click", (event) => {{
          event.stopPropagation();
          const columnKey = button.dataset.filterColumn;
          const popover = document.getElementById("filterPopover");
          if (state.activeFilterColumn === columnKey && popover.classList.contains("open")) {{
            closeFilterPopover();
          }} else {{
            openFilterPopover(columnKey, button);
          }}
        }});
      }});
      document.getElementById("filterSummary").textContent = `Showing ${{filtered.length}} of ${{payload.signals.length}} rows.`;
    }}

    function wireFilters() {{
      document.getElementById("filterMinValue").addEventListener("input", () => {{
        if (!state.activeFilterColumn) return;
        const min = parseFilterNumber(document.getElementById("filterMinValue").value);
        const max = parseFilterNumber(document.getElementById("filterMaxValue").value);
        if (min === null && max === null) {{
          delete state.columnFilters[state.activeFilterColumn];
        }} else {{
          state.columnFilters[state.activeFilterColumn] = {{ type: "range", min, max }};
        }}
        renderDatasetTable();
      }});
      document.getElementById("filterMaxValue").addEventListener("input", () => {{
        if (!state.activeFilterColumn) return;
        const min = parseFilterNumber(document.getElementById("filterMinValue").value);
        const max = parseFilterNumber(document.getElementById("filterMaxValue").value);
        if (min === null && max === null) {{
          delete state.columnFilters[state.activeFilterColumn];
        }} else {{
          state.columnFilters[state.activeFilterColumn] = {{ type: "range", min, max }};
        }}
        renderDatasetTable();
      }});
      document.getElementById("clearFilterButton").addEventListener("click", () => {{
        if (state.activeFilterColumn) delete state.columnFilters[state.activeFilterColumn];
        document.getElementById("filterMinValue").value = "";
        document.getElementById("filterMaxValue").value = "";
        renderDatasetTable();
        renderFilterOptions();
      }});
      document.addEventListener("click", (event) => {{
        const popover = document.getElementById("filterPopover");
        if (!popover.classList.contains("open")) return;
        if (popover.contains(event.target)) return;
        if (event.target.closest("[data-filter-column]")) return;
        closeFilterPopover();
      }});
    }}

    function renderLineChart(targetId, rows, valueKey, colorOffset) {{
      const container = document.getElementById(targetId);
      const grouped = new Map();
      rows.forEach((row) => {{
        if (row.status !== "ok") return;
        const values = grouped.get(row.ticker) || [];
        values.push(row);
        grouped.set(row.ticker, values);
      }});
      const all = Array.from(grouped.values()).flat();
      if (!all.length) {{
        container.innerHTML = "<p>No successful signals available.</p>";
        return;
      }}
      const width = 720;
      const height = 260;
      const pad = {{ top: 18, right: 14, bottom: 28, left: 44 }};
      const min = Math.min(...all.map((row) => Number(row[valueKey])));
      const max = Math.max(...all.map((row) => Number(row[valueKey])));
      const span = Math.max(max - min, 1);
      const grid = [0, 0.5, 1].map((fraction) => {{
        const y = pad.top + fraction * (height - pad.top - pad.bottom);
        const value = max - fraction * span;
        return `<g>
          <line x1="${{pad.left}}" y1="${{y}}" x2="${{width - pad.right}}" y2="${{y}}" stroke="var(--border)" />
          <text x="${{pad.left - 8}}" y="${{y + 4}}" text-anchor="end" font-size="11" fill="var(--text-secondary)">${{fmt(value)}}</text>
        </g>`;
      }}).join("");

      const paths = Array.from(grouped.entries()).map(([ticker, items], index) => {{
        const sorted = items.slice().sort((left, right) => left.run_timestamp.localeCompare(right.run_timestamp));
        const points = sorted.map((item, itemIndex) => {{
          const x = pad.left + (itemIndex / Math.max(sorted.length - 1, 1)) * (width - pad.left - pad.right);
          const y = height - pad.bottom - ((Number(item[valueKey]) - min) / span) * (height - pad.top - pad.bottom);
          return [x, y, item];
        }});
        const color = palette[(index + colorOffset) % palette.length];
        const path = points.map((point, pointIndex) => `${{pointIndex === 0 ? "M" : "L"}} ${{point[0].toFixed(1)}} ${{point[1].toFixed(1)}}`).join(" ");
        const circles = points.map((point) => `<circle cx="${{point[0].toFixed(1)}}" cy="${{point[1].toFixed(1)}}" r="3.5" fill="${{color}}">
          <title>${{ticker}} · ${{point[2].run_timestamp}} · ${{valueKey}}=${{fmt(point[2][valueKey])}}</title>
        </circle>`).join("");
        return `<path d="${{path}}" fill="none" stroke="${{color}}" stroke-width="2.5"/>${{circles}}`;
      }}).join("");

      container.innerHTML = `
        <svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="${{valueKey}} chart">
          <line x1="${{pad.left}}" y1="${{height - pad.bottom}}" x2="${{width - pad.right}}" y2="${{height - pad.bottom}}" stroke="var(--border)" />
          <line x1="${{pad.left}}" y1="${{pad.top}}" x2="${{pad.left}}" y2="${{height - pad.bottom}}" stroke="var(--border)" />
          ${{grid}}
          ${{paths}}
        </svg>`;
    }}

    function renderAvailabilityChart() {{
      const rows = payload.status_rows;
      const container = document.getElementById("availabilityChart");
      if (!rows.length) {{
        container.innerHTML = "<p>No run data available.</p>";
        return;
      }}
      const width = 720;
      const height = 260;
      const pad = {{ top: 18, right: 14, bottom: 28, left: 44 }};
      const maxTotal = Math.max(...rows.map((row) => row.ok + row.unavailable), 1);
      const step = (width - pad.left - pad.right) / rows.length;
      const barWidth = Math.max(12, step * 0.62);
      const bars = rows.map((row, index) => {{
        const x = pad.left + index * step + (step - barWidth) / 2;
        const okHeight = (row.ok / maxTotal) * (height - pad.top - pad.bottom);
        const unavailableHeight = (row.unavailable / maxTotal) * (height - pad.top - pad.bottom);
        const okY = height - pad.bottom - okHeight;
        const unavailableY = okY - unavailableHeight;
        return `
          <rect x="${{x}}" y="${{okY}}" width="${{barWidth}}" height="${{okHeight}}" fill="var(--positive)">
            <title>${{row.run_timestamp}} · ok=${{row.ok}}</title>
          </rect>
          <rect x="${{x}}" y="${{unavailableY}}" width="${{barWidth}}" height="${{unavailableHeight}}" fill="var(--negative)">
            <title>${{row.run_timestamp}} · unavailable=${{row.unavailable}}</title>
          </rect>`;
      }}).join("");
      container.innerHTML = `
        <svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="availability chart">
          <line x1="${{pad.left}}" y1="${{height - pad.bottom}}" x2="${{width - pad.right}}" y2="${{height - pad.bottom}}" stroke="var(--border)" />
          <line x1="${{pad.left}}" y1="${{pad.top}}" x2="${{pad.left}}" y2="${{height - pad.bottom}}" stroke="var(--border)" />
          ${{bars}}
        </svg>`;
    }}

    function activateTab(tabName) {{
      document.querySelectorAll(".tab-button").forEach((button) => {{
        button.classList.toggle("active", button.dataset.tab === tabName);
      }});
      document.querySelectorAll(".tab-panel").forEach((panel) => {{
        panel.classList.toggle("active", panel.id === `${{tabName}}Tab`);
      }});
    }}

    document.querySelectorAll(".tab-button").forEach((button) => {{
      button.addEventListener("click", () => activateTab(button.dataset.tab));
    }});

    document.getElementById("themeToggle").addEventListener("click", () => {{
      const root = document.documentElement;
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next === "dark" ? "dark" : "";
      document.getElementById("themeToggle").textContent = next === "dark" ? "Light" : "Dark";
    }});

    renderCards();
    wireFilters();
    renderLineChart("rawScoreChart", payload.signals, "raw_score", 0);
    renderLineChart("confidenceChart", payload.signals, "confidence", 2);
    renderAvailabilityChart();
    renderTable("summaryTable", payload.summary_rows, [
      {{ key: "ticker", label: "Ticker" }},
      {{ key: "runs", label: "Runs" }},
      {{ key: "avg_confidence", label: "Avg Confidence" }},
      {{ key: "avg_raw_score", label: "Avg Raw Score" }},
      {{ key: "bullish_rate", label: "Bullish Rate" }},
      {{ key: "bearish_rate", label: "Bearish Rate" }},
    ]);
    renderDatasetTable();
    document.getElementById("fieldReference").innerHTML = payload.field_reference_html;
    document.getElementById("validationReference").innerHTML = payload.validation_html;
  </script>
</body>
</html>
"""


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
