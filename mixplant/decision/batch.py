"""The registry of production batches the plant has declared."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import DuplicateError, NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class Batch:
    """One declared production batch."""

    batch_id: str
    generation: int
    tick: int
    grade: str
    quantity: float
    unit: str = "m3"

    def describe(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "generation": self.generation,
            "tick": self.tick,
            "grade": self.grade,
            "quantity": self.quantity,
            "unit": self.unit,
        }


class BatchRegistry:
    """Keeps every declared batch, oldest first."""

    __slots__ = ("_batches",)

    def __init__(self) -> None:
        self._batches: list[Batch] = []

    def declare(
        self,
        batch_id: str,
        *,
        tick: int,
        generation: int,
        grade: str,
        quantity: float,
        unit: str = "m3",
    ) -> Batch:
        """Register a new batch and refuse a reused identity."""

        if not batch_id:
            raise ValidationError("batch identity must not be empty")
        if quantity <= 0:
            raise ValidationError("batch quantity must be positive", quantity=quantity)
        if self.find(batch_id) is not None:
            raise DuplicateError("batch identity was reused", batch_id=batch_id)
        batch = Batch(
            batch_id=batch_id,
            generation=generation,
            tick=tick,
            grade=grade,
            quantity=quantity,
            unit=unit,
        )
        self._batches.append(batch)
        return batch

    def adopt(self, batch: Batch) -> Batch:
        """Adopt a batch read back from the stream after a restart."""

        if self.find(batch.batch_id) is None:
            self._batches.append(batch)
        return batch

    def find(self, batch_id: str) -> Batch | None:
        for batch in self._batches:
            if batch.batch_id == batch_id:
                return batch
        return None

    def require(self, batch_id: str) -> Batch:
        batch = self.find(batch_id)
        if batch is None:
            raise NotFoundError("batch was never declared", batch_id=batch_id)
        return batch

    def all(self) -> tuple[Batch, ...]:
        return tuple(self._batches)

    def latest(self) -> Batch | None:
        return self._batches[-1] if self._batches else None

    def count(self) -> int:
        return len(self._batches)
