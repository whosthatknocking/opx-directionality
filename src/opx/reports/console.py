from __future__ import annotations

from opx.models import BatchRunResult


def render_console_report(batch: BatchRunResult) -> str:
    lines = [
        f"run_id={batch.run.run_id}",
        f"signal_time_et={batch.run.signal_time_et}",
        f"provider={batch.run.provider_name}",
        f"log_path={batch.run.log_path}",
        "",
    ]
    for signal in batch.signals:
        if signal.status != "ok":
            lines.append(f"{signal.ticker}: unavailable ({signal.reason})")
            continue
        lines.append(
            f"{signal.ticker}: bias={signal.bias} confidence={signal.confidence} "
            f"regime={signal.regime} posture={signal.option_posture} score={signal.raw_score}"
        )
    return "\n".join(lines)
