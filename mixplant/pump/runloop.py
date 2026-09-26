"""Accumulates the strokes of one pumping run."""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from .stroke import StrokeRecord


class RunLoop:
    """Keeps the strokes and delivered volume of the current run."""

    __slots__ = ("_strokes", "_running")

    def __init__(self) -> None:
        self._strokes: list[StrokeRecord] = []
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Begin a run, refusing a second run over the top of the first."""

        if self._running:
            raise NotFoundError("the pump is already running")
        self._running = True
        self._strokes = []

    def add(self, volume_m3: float) -> StrokeRecord:
        """Record one stroke and return it."""

        if not self._running:
            raise NotFoundError("the pump is not running")
        from .stroke import stroke_record

        record = stroke_record(index=len(self._strokes) + 1, volume_m3=volume_m3)
        self._strokes.append(record)
        return record

    def stop(self) -> None:
        self._running = False

    def strokes(self) -> tuple[StrokeRecord, ...]:
        return tuple(self._strokes)

    @property
    def volume_m3(self) -> float:
        return round(sum(record.volume_m3 for record in self._strokes), 4)

    def describe(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "strokes": len(self._strokes),
            "volume_m3": self.volume_m3,
        }
