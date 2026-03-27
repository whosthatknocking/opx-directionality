from __future__ import annotations

import logging
from pathlib import Path


def setup_run_logger(log_dir: str | Path, run_id: str) -> tuple[logging.Logger, Path]:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    run_log_path = directory / f"{run_id}.log"

    logger = logging.getLogger(f"opx.run.{run_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.FileHandler(run_log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger, run_log_path


def append_aggregate_run_log(log_dir: str | Path, filename: str, line: str) -> Path:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")
    return path
