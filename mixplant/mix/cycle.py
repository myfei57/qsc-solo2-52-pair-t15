"""Which batch the mixer is currently working on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class Cycle:
    """One mixing cycle bound to a batch and a recipe version."""

    batch_id: str
    version: int
    tick: int

    def describe(self) -> dict[str, Any]:
        return {"active": True, "batch_id": self.batch_id, "version": self.version, "tick": self.tick}


class CycleTracker:
    """Remembers the cycle that is currently on the mixer."""

    __slots__ = ("_current", "_completed")

    def __init__(self) -> None:
        self._current: Cycle | None = None
        self._completed: list[str] = []

    def begin(self, batch_id: str, version: int, *, tick: int) -> Cycle:
        """Start a cycle; a mixer may only run one cycle at a time."""

        if not batch_id:
            raise ValidationError("a cycle needs a batch identity")
        if self._current is not None:
            raise ValidationError(
                "the mixer is already running a cycle",
                batch_id=self._current.batch_id,
                requested=batch_id,
            )
        self._current = Cycle(batch_id=batch_id, version=version, tick=tick)
        return self._current

    def complete(self, *, tick: int) -> Cycle:
        """Finish the cycle on the mixer and remember the batch."""

        if self._current is None:
            raise NotFoundError("no mixing cycle is running")
        done = self._current
        self._completed.append(done.batch_id)
        self._current = None
        return done

    def current(self) -> Cycle | None:
        return self._current

    def require_current(self) -> Cycle:
        if self._current is None:
            raise NotFoundError("no mixing cycle is running")
        return self._current

    def completed(self) -> tuple[str, ...]:
        return tuple(self._completed)
