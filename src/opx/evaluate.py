from __future__ import annotations

import argparse

from opx.config import DEFAULT_CONFIG_PATH, load_config
from opx.evaluation import evaluate_canonical_batches
from opx.providers import create_provider
from opx.storage import create_signal_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate canonical opx-directionality runs "
            "against realized outcomes."
        )
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to engine config TOML.",
    )
    parser.add_argument("--storage-kind", help="Override storage backend from config.")
    parser.add_argument("--storage-target", help="Override storage target from config.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of historical runs to evaluate.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    store = create_signal_store(
        args.storage_kind or config.storage.kind,
        args.storage_target or config.storage.target,
    )
    batches = store.load_batches(limit=args.limit)
    if not batches:
        print("no persisted runs found")
        return 1

    updated = evaluate_canonical_batches(batches, create_provider(config))
    for batch in updated:
        store.save_batch(batch)

    evaluated_signals = sum(
        1
        for batch in updated
        for signal in batch.signals
        if signal.realized_return_pct is not None
    )
    print(f"runs={len(updated)} evaluated_signals={evaluated_signals}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
