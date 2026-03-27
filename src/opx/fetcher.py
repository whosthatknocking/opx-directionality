from __future__ import annotations

import argparse

from opx.config import DEFAULT_CONFIG_PATH, load_config
from opx.pipeline import run_daily_engine
from opx.reports.console import render_console_report
from opx.storage import create_signal_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the post-open directionality engine.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to engine config TOML.",
    )
    parser.add_argument("--storage-kind", help="Override storage backend from config.")
    parser.add_argument("--storage-target", help="Override storage target from config.")
    parser.add_argument("--no-persist", action="store_true", help="Skip persistence.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    batch = run_daily_engine(config)
    print(render_console_report(batch))

    if not args.no_persist:
        store = create_signal_store(
            args.storage_kind or config.storage.kind,
            args.storage_target or config.storage.target,
        )
        store.initialize()
        store.save_batch(batch)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
