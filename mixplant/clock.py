"""Tick source for the control decisions.

Nothing in the runtime reads the wall clock.  A tick only moves when a caller
asks for it, so the same command sequence always produces the same decisions
and the same persisted records.
"""

from __future__ import annotations

from typing import Protocol


class Clock(Protocol):
    """Minimal tick source used by every service."""

    def now(self) -> int:
        """Return the current tick."""

    def advance(self, ticks: int = 1) -> int:
        """Move the tick forward and return the new value."""


class ManualClock:
    """A clock that moves only when it is told to."""

    __slots__ = ("_tick",)

    def __init__(self, start: int = 0) -> None:
        if start < 0:
            raise ValueError("start tick must not be negative")
        self._tick = start

    def now(self) -> int:
        return self._tick

    def advance(self, ticks: int = 1) -> int:
        if ticks < 0:
            raise ValueError("cannot move the tick backwards")
        self._tick += ticks
        return self._tick


class Timer:
    """A countdown that starts at a tick and finishes ``length`` ticks later."""

    __slots__ = ("_started", "_length")

    def __init__(self, length: int) -> None:
        if length < 0:
            raise ValueError("timer length must not be negative")
        self._started: int | None = None
        self._length = length

    @property
    def length(self) -> int:
        return self._length

    @property
    def running(self) -> bool:
        return self._started is not None

    def start(self, tick: int) -> int:
        """Begin the countdown and return the tick it will finish on."""

        if tick < 0:
            raise ValueError("tick must not be negative")
        self._started = tick
        return self.deadline

    @property
    def deadline(self) -> int:
        if self._started is None:
            raise ValueError("timer was never started")
        return self._started + self._length

    def remaining(self, now: int) -> int:
        """Return how many ticks are left, never below zero."""

        if self._started is None:
            return self._length
        return max(0, self.deadline - now)

    def elapsed(self, now: int) -> bool:
        """Return whether the countdown has finished by ``now``."""

        if self._started is None:
            return False
        return now >= self.deadline

    def cancel(self) -> None:
        self._started = None

    def sync(self, *, started: int | None, length: int) -> None:
        """Adopt a countdown read back from the stream after a restart."""

        self._started = started
        self._length = max(0, length)

    def describe(self, now: int) -> dict[str, int | bool | None]:
        return {
            "started": self._started,
            "length": self._length,
            "running": self.running,
            "remaining": self.remaining(now),
            "finished": self.elapsed(now),
        }
