"""Scale calibration: a slope and an offset applied to raw readings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class Calibration:
    """The correction applied to every raw scale reading."""

    slope: float = 1.0
    offset: float = 0.0

    def __post_init__(self) -> None:
        if self.slope <= 0:
            raise ValidationError("calibration slope must be positive", slope=self.slope)

    def apply(self, raw_kg: float) -> float:
        """Return the corrected mass."""

        return round(raw_kg * self.slope + self.offset, 4)

    def describe(self) -> dict[str, Any]:
        return {"slope": self.slope, "offset": self.offset}


def calibrate(*, slope: float, offset: float) -> Calibration:
    """Build a calibration from a console request."""

    return Calibration(slope=slope, offset=offset)
