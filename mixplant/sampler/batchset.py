"""Which batches have already been sampled."""

from __future__ import annotations

from typing import Any

from ..errors import DuplicateError


class BatchSet:
    """Remembers the batches that already produced a sample."""

    __slots__ = ("_drawn",)

    def __init__(self) -> None:
        self._drawn: list[str] = []

    def add(self, batch_id: str) -> None:
        if batch_id in self._drawn:
            raise DuplicateError("batch already produced a sample", batch_id=batch_id)
        self._drawn.append(batch_id)

    def drawn(self) -> tuple[str, ...]:
        return tuple(self._drawn)

    def contains(self, batch_id: str) -> bool:
        return batch_id in self._drawn

    def count(self) -> int:
        return len(self._drawn)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "drawn": list(self._drawn), "count": self.count()}
