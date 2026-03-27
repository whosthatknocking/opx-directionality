from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from opx.models import BatchRunResult


def canonical_group_key(batch: BatchRunResult) -> tuple[str, str, str, str]:
    run = batch.run
    return (run.trade_date, run.signal_time_et, run.provider_name, run.config_fingerprint)


def apply_canonical_selection(batches: list[BatchRunResult]) -> list[BatchRunResult]:
    if not batches:
        return []

    groups: dict[tuple[str, str, str, str], list[BatchRunResult]] = {}
    for batch in batches:
        groups.setdefault(canonical_group_key(batch), []).append(batch)

    updated: list[BatchRunResult] = []
    for group in groups.values():
        winner = _select_winner(group)
        if winner is None:
            updated.extend(group)
            continue
        full = (
            winner.run.validation_state == "valid"
            and winner.run.completion_rate >= 1.0
        )
        reason = "earliest_complete_post_signal" if full else "best_available_partial"
        status = "canonical" if full else "partial_canonical"

        for batch in group:
            if batch.run.run_id == winner.run.run_id:
                updated.append(
                    BatchRunResult(
                        run=replace(batch.run, selection_status=status, selection_reason=reason),
                        signals=batch.signals,
                    )
                )
                continue

            loser_status = batch.run.selection_status
            loser_reason = batch.run.selection_reason
            if batch.run.signal_time_reached:
                loser_status = "retry"
                loser_reason = (
                    f"superseded_by={winner.run.run_id}"
                )
            updated.append(
                BatchRunResult(
                    run=replace(
                        batch.run,
                        selection_status=loser_status,
                        selection_reason=loser_reason,
                    ),
                    signals=batch.signals,
                )
            )
    return sorted(updated, key=lambda batch: batch.run.run_timestamp)


def _select_winner(group: list[BatchRunResult]) -> BatchRunResult | None:
    eligible = [
        batch
        for batch in group
        if batch.run.signal_time_reached and batch.run.validation_state != "invalid"
    ]
    if not eligible:
        return None

    full = [
        batch
        for batch in eligible
        if batch.run.validation_state == "valid"
        and batch.run.completion_rate >= 1.0
    ]
    if full:
        return min(full, key=lambda batch: batch.run.run_timestamp)

    return max(
        eligible,
        key=lambda batch: (
            _validation_rank(batch.run.validation_state),
            batch.run.completion_rate,
            -_timestamp_rank(batch.run.run_timestamp),
        ),
    )


def _validation_rank(state: str) -> int:
    return {"invalid": 0, "partial": 1, "valid": 2}.get(state, 0)


def _timestamp_rank(value: datetime) -> float:
    return value.timestamp()
