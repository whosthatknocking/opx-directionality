from __future__ import annotations
# pylint: disable=line-too-long

import json
from datetime import datetime
from pathlib import Path

from opx.canonical import apply_canonical_selection, canonical_group_key
from opx.models import BatchRunResult, SignalResult, SignalRunRecord
from opx.storage.base import SignalStore


class FileSignalStore(SignalStore):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def save_batch(self, batch: BatchRunResult) -> None:
        self.initialize()
        existing = [stored for stored in self.load_batches() if stored.run.run_id != batch.run.run_id]
        selected = apply_canonical_selection(existing + [batch])
        for stored in selected:
            path = self.root / f"{stored.run.run_id}.json"
            path.write_text(json.dumps(stored.to_dict(), indent=2))
        self._write_canonical_index(selected)

    def load_batches(self, limit: int | None = None) -> list[BatchRunResult]:
        if not self.root.exists():
            return []
        paths = sorted(path for path in self.root.glob("*.json") if not path.name.startswith("_"))
        if limit is not None:
            paths = paths[-limit:]
        return [_deserialize_batch(json.loads(path.read_text())) for path in paths]

    def _write_canonical_index(self, batches: list[BatchRunResult]) -> None:
        index = {}
        for batch in batches:
            if batch.run.selection_status not in {"canonical", "partial_canonical"}:
                continue
            key = "|".join(canonical_group_key(batch))
            index[key] = {
                "run_id": batch.run.run_id,
                "selection_status": batch.run.selection_status,
                "selection_reason": batch.run.selection_reason,
            }
        (self.root / "_canonical_index.json").write_text(json.dumps(index, indent=2))


def _deserialize_batch(payload: dict) -> BatchRunResult:
    run_payload = payload["run"]
    run = SignalRunRecord(
        run_id=run_payload["run_id"],
        run_timestamp=datetime.fromisoformat(run_payload["run_timestamp"]),
        trade_date=run_payload["trade_date"],
        signal_time_et=run_payload["signal_time_et"],
        provider_name=run_payload["provider_name"],
        engine_version=run_payload["engine_version"],
        config_version=run_payload["config_version"],
        config_fingerprint=run_payload["config_fingerprint"],
        tickers=list(run_payload["tickers"]),
        signal_time_reached=bool(run_payload["signal_time_reached"]),
        completion_rate=float(run_payload.get("completion_rate", 0.0)),
        validation_state=run_payload.get("validation_state", "valid"),
        validation_issues=list(run_payload.get("validation_issues", [])),
        selection_status=run_payload.get("selection_status", "candidate"),
        selection_reason=run_payload.get("selection_reason", "awaiting_canonical_selection"),
        log_path=run_payload.get("log_path"),
    )
    signals = [
        SignalResult(
            ticker=signal["ticker"],
            signal_time=datetime.fromisoformat(signal["signal_time"]),
            bias=signal["bias"],
            confidence=int(signal["confidence"]),
            regime=signal["regime"],
            option_posture=signal["option_posture"],
            raw_score=int(signal["raw_score"]),
            factors=dict(signal["factors"]),
            factor_summary=list(signal["factor_summary"]),
            status=signal.get("status", "ok"),
            reason=signal.get("reason"),
            validation_state=signal.get("validation_state", "valid"),
            validation_issues=list(signal.get("validation_issues", [])),
            signal_price=signal.get("signal_price"),
            realized_close=signal.get("realized_close"),
            realized_return_pct=signal.get("realized_return_pct"),
            realized_outcome=signal.get("realized_outcome"),
            directional_hit=signal.get("directional_hit"),
        )
        for signal in payload.get("signals", [])
    ]
    return BatchRunResult(run=run, signals=signals)
