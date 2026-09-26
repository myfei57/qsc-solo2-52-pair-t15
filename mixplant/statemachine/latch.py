"""Latches whose set and clear order is enforced."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import OrderViolationError


@dataclass(frozen=True, slots=True)
class LatchEvent:
    """One set or clear of a latch."""

    latch: str
    latched: bool
    step: int
    tick: int
    reason: str

    def describe(self) -> dict[str, object]:
        return {
            "latch": self.latch,
            "latched": self.latched,
            "step": self.step,
            "tick": self.tick,
            "reason": self.reason,
        }


class Latch:
    """A named latch that must be set before it can be cleared."""

    __slots__ = ("_name", "_latched", "_step", "_reason", "_events")

    def __init__(self, name: str) -> None:
        self._name = name
        self._latched = False
        self._step = 0
        self._reason = "initial"
        self._events: list[LatchEvent] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def latched(self) -> bool:
        return self._latched

    @property
    def step(self) -> int:
        return self._step

    @property
    def reason(self) -> str:
        return self._reason

    def history(self) -> tuple[LatchEvent, ...]:
        return tuple(self._events)

    def set(self, *, tick: int, reason: str) -> LatchEvent:
        """Raise the latch."""

        if self._latched:
            raise OrderViolationError("latch is already set", latch=self._name, reason=self._reason)
        return self._move(latched=True, tick=tick, reason=reason)

    def clear(self, *, tick: int, reason: str) -> LatchEvent:
        """Drop the latch."""

        if not self._latched:
            raise OrderViolationError("latch was never set", latch=self._name, reason=self._reason)
        return self._move(latched=False, tick=tick, reason=reason)

    def sync(self, *, latched: bool, step: int, reason: str) -> None:
        """Adopt the latch position recorded in the stream."""

        self._latched = latched
        self._step = max(0, step)
        self._reason = reason

    def _move(self, *, latched: bool, tick: int, reason: str) -> LatchEvent:
        self._latched = latched
        self._step += 1
        self._reason = reason
        event = LatchEvent(latch=self._name, latched=latched, step=self._step, tick=tick, reason=reason)
        self._events.append(event)
        return event

    def describe(self) -> dict[str, object]:
        return {
            "latch": self._name,
            "latched": self._latched,
            "step": self._step,
            "reason": self._reason,
            "transitions": len(self._events),
        }
