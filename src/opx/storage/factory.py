from __future__ import annotations

from pathlib import Path

from opx.storage.base import SignalStore
from opx.storage.file_store import FileSignalStore
from opx.storage.sqlite_store import SQLiteSignalStore


def create_signal_store(kind: str, target: str | Path) -> SignalStore:
    normalized_kind = kind.lower()
    if normalized_kind == "file":
        return FileSignalStore(target)
    if normalized_kind == "sqlite":
        return SQLiteSignalStore(target)
    raise ValueError(f"unsupported storage backend: {kind}")
