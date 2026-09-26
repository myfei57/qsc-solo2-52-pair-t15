"""The mixing window that gates the discharge door."""

from __future__ import annotations

from typing import Any

from ..clock import Timer
from ..errors import OrderViolationError


class MixTimer:
    """Wraps the deterministic timer and describes it for the record stream."""

    __slots__ = ("_timer",)

    def __init__(self) -> None:
        self._timer = Timer(0)

    @property
    def length(self) -> int:
        return self._timer.length

    @property
    def running(self) -> bool:
        return self._timer.running

    def start(self, *, tick: int, length: int) -> int:
        """Start the mixing window and return the tick it finishes on."""

        if length < 1:
            raise OrderViolationError("mixing window must be at least one tick", length=length)
        if self._timer.running:
            raise OrderViolationError("the mixing window is already running", started=True)
        self._timer = Timer(length)
        return self._timer.start(tick)

    def finished(self, now: int) -> bool:
        """Return whether the window has finished by ``now``."""

        return self._timer.elapsed(now)

    def require_finished(self, now: int) -> None:
        """Refuse the call while the window is still open."""

        if not self._timer.running:
            raise OrderViolationError("the mixing window was never started")
        if not self._timer.elapsed(now):
            raise OrderViolationError(
                "the mixing window has not finished yet",
                remaining=self._timer.remaining(now),
                deadline=self._timer.deadline,
            )

    def cancel(self) -> None:
        self._timer.cancel()

    def sync(self, *, started: int | None, length: int) -> None:
        self._timer.sync(started=started, length=length)

    def payload(self, now: int, *, finished: bool) -> dict[str, Any]:
        """Build the timer record body."""

        return {
            "active": True,
            "finished": finished,
            "remaining": self._timer.remaining(now),
            "length": self._timer.length,
            "started": None if not self._timer.running else self._timer.describe(now)["started"],
        }
