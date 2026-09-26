"""One pump stroke and the volume it delivered."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class StrokeRecord:
    """The volume one stroke pushed into the line."""

    index: int
    volume_m3: float

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValidationError("stroke index starts at one", index=self.index)
        if self.volume_m3 <= 0:
            raise ValidationError("a stroke needs a positive volume", index=self.index)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "index": self.index, "volume_m3": self.volume_m3}


def stroke_record(*, index: int, volume_m3: float) -> StrokeRecord:
    """Build one stroke record."""

    return StrokeRecord(index=index, volume_m3=round(volume_m3, 4))
