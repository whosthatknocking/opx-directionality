from __future__ import annotations

import argparse

import pandas as pd

from opx.storage import create_signal_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visualize and evaluate multiple opx-directionality runs.")
    parser.add_argument("--storage-kind", default="file", help="Storage backend to read from.")
    parser.add_argument("--storage-target", default="output/runs", help="Storage location to read from.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of historical runs to load.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    store = create_signal_store(args.storage_kind, args.storage_target)
    batches = store.load_batches(limit=args.limit)
    if not batches:
        print("no persisted runs found")
        return 1

    frame = _flatten_batches(batches)
    _print_summary(frame)
    _plot(frame)
    return 0


def _flatten_batches(batches) -> pd.DataFrame:
    rows = []
    for batch in batches:
        for signal in batch.signals:
            rows.append(
                {
                    "run_id": batch.run.run_id,
                    "run_timestamp": batch.run.run_timestamp,
                    "provider_name": batch.run.provider_name,
                    "ticker": signal.ticker,
                    "status": signal.status,
                    "bias": signal.bias,
                    "confidence": signal.confidence,
                    "regime": signal.regime,
                    "raw_score": signal.raw_score,
                }
            )
    return pd.DataFrame(rows).sort_values(["ticker", "run_timestamp"])


def _print_summary(frame: pd.DataFrame) -> None:
    available = frame[frame["status"] == "ok"]
    print(f"runs={frame['run_id'].nunique()} tickers={frame['ticker'].nunique()} signals={len(frame)}")
    if not available.empty:
        grouped = available.groupby("ticker").agg(
            avg_confidence=("confidence", "mean"),
            avg_raw_score=("raw_score", "mean"),
            bullish_rate=("bias", lambda values: (values == "bullish").mean()),
            bearish_rate=("bias", lambda values: (values == "bearish").mean()),
        )
        print(grouped.round(2).to_string())


def _plot(frame: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise SystemExit(f"matplotlib is required for plotting: {exc}") from exc

    available = frame[frame["status"] == "ok"]
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)

    for ticker, subset in available.groupby("ticker"):
        axes[0].plot(subset["run_timestamp"], subset["raw_score"], marker="o", label=ticker)
        axes[1].plot(subset["run_timestamp"], subset["confidence"], marker="o", label=ticker)

    status_counts = frame.groupby(["run_timestamp", "status"]).size().unstack(fill_value=0)
    status_counts.plot(kind="bar", stacked=True, ax=axes[2], width=0.9)

    axes[0].set_title("Raw Score By Run")
    axes[0].set_ylabel("Raw Score")
    axes[1].set_title("Confidence By Run")
    axes[1].set_ylabel("Confidence")
    axes[2].set_title("Signal Availability By Run")
    axes[2].set_ylabel("Count")
    axes[2].set_xlabel("Run Timestamp")

    if not available.empty:
        axes[0].legend(loc="best", ncols=2)
        axes[1].legend(loc="best", ncols=2)

    plt.tight_layout()
    plt.show()
