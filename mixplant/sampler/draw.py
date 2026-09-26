"""One sample drawn from a batch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class DrawRecord:
    """The sample taken from one batch."""

    batch_id: str
    litres: float
    tick: int

    def __post_init__(self) -> None:
        if not self.batch_id:
            raise ValidationError("a sample draw needs a batch identity")
        if self.litres <= 0:
            raise ValidationError("a sample draw needs a positive volume", batch_id=self.batch_id)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "batch_id": self.batch_id, "litres": self.litres, "tick": self.tick}


def draw_record(*, batch_id: str, litres: float, tick: int) -> DrawRecord:
    """Build one draw record."""

    return DrawRecord(batch_id=batch_id, litres=round(litres, 4), tick=tick)
