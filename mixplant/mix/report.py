"""The mixing report the audit log keeps."""

from __future__ import annotations

from typing import Any, Mapping

from .cycle import Cycle
from .timer import MixTimer


def mix_report(
    *,
    cycle: Cycle,
    timer: MixTimer,
    now: int,
    inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Summarise one finished mixing cycle."""

    return {
        "batch_id": cycle.batch_id,
        "version": cycle.version,
        "started": cycle.tick,
        "finished": now,
        "window_ticks": timer.length,
        "finished_window": timer.finished(now),
        "inputs": dict(inputs or {}),
    }
