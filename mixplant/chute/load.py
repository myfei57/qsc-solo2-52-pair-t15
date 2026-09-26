"""One truck load taken from the discharge door."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class LoadRecord:
    """One load handed to a truck."""

    truck_id: str
    batch_id: str
    volume_m3: float
    tick: int

    def __post_init__(self) -> None:
        if not self.truck_id:
            raise ValidationError("a load needs a truck identity")
        if self.volume_m3 <= 0:
            raise ValidationError("a load needs a positive volume", truck=self.truck_id)

    def describe(self) -> dict[str, Any]:
        return {
            "active": True,
            "truck_id": self.truck_id,
            "batch_id": self.batch_id,
            "volume_m3": self.volume_m3,
            "tick": self.tick,
        }


def load_record(*, truck_id: str, batch_id: str, volume_m3: float, tick: int) -> LoadRecord:
    """Build one load record."""

    return LoadRecord(truck_id=truck_id, batch_id=batch_id, volume_m3=round(volume_m3, 4), tick=tick)
