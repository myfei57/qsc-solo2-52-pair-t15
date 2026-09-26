"""When a mix is due to be sampled."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..config import Limits
from ..errors import NotFoundError


@dataclass(frozen=True, slots=True)
class SampleDue:
    """Whether the current batch should be sampled, and why."""

    due: bool
    batch_id: str
    reason: str

    def describe(self) -> dict[str, Any]:
        return {"due": self.due, "batch_id": self.batch_id, "reason": self.reason}


def _timer_entry(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    group = state.get("mix")
    if not isinstance(group, Mapping):
        return None
    entry = group.get("timer")
    return entry if isinstance(entry, Mapping) else None


def sample_due(*, state: Mapping[str, Any], limits: Limits, batch_id: str, now: int) -> SampleDue:
    """Decide whether the finished mix should be handed to the sampler."""

    timer = _timer_entry(state)
    if timer is None or not timer.get("finished"):
        return SampleDue(due=False, batch_id=batch_id, reason="the mixing window has not finished")
    started = timer.get("started")
    if isinstance(started, int) and now - started > limits.sample_window_ticks:
        return SampleDue(due=True, batch_id=batch_id, reason="the sampling window is open")
    return SampleDue(due=True, batch_id=batch_id, reason="the freshly mixed batch is due for a sample")


def require_batch(batch_id: str | None) -> str:
    """Return the batch identity a schedule needs."""

    if not batch_id:
        raise NotFoundError("no batch is running to schedule a sample for")
    return batch_id
