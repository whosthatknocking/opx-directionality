from __future__ import annotations
# pylint: disable=line-too-long

from opx.models import BatchRunResult


def render_console_report(batch: BatchRunResult) -> str:
    ok_count = sum(1 for signal in batch.signals if signal.status == "ok")
    unavailable_count = sum(1 for signal in batch.signals if signal.status != "ok")
    valid_count = sum(1 for signal in batch.signals if signal.validation_state == "valid")
    partial_count = sum(1 for signal in batch.signals if signal.validation_state == "partial")
    invalid_count = sum(1 for signal in batch.signals if signal.validation_state == "invalid")

    lines = [
        f"run_id={batch.run.run_id}",
        f"signal_time_et={batch.run.signal_time_et}",
        f"provider={batch.run.provider_name}",
        f"validation_state={batch.run.validation_state}",
        f"selection_status={batch.run.selection_status}",
        f"completion_rate={batch.run.completion_rate:.2f}",
        f"log_path={batch.run.log_path}",
        "",
    ]
    for signal in batch.signals:
        if signal.status != "ok":
            lines.append(f"{signal.ticker}: unavailable ({signal.reason})")
            continue
        lines.append(
            f"{signal.ticker}: bias={signal.bias} confidence={signal.confidence} "
            f"regime={signal.regime} posture={signal.option_posture} score={signal.raw_score} "
            f"validation={signal.validation_state}"
        )

    lines.extend(
        [
            "",
            "summary:",
            f"signals_total={len(batch.signals)} ok={ok_count} unavailable={unavailable_count}",
            f"validation_valid={valid_count} validation_partial={partial_count} validation_invalid={invalid_count}",
            (
                f"run_status={batch.run.validation_state} "
                f"selection={batch.run.selection_status} "
                f"completion_rate={batch.run.completion_rate:.2f}"
            ),
        ]
    )
    return "\n".join(lines)
