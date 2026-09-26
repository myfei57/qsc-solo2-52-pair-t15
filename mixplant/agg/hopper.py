"""The scale hopper that must be emptied before the mixer stops."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class HopperState:
    """How much material the scale hopper still holds."""

    residual_kg: float
    released: bool

    def __post_init__(self) -> None:
        if self.residual_kg < 0:
            raise ValidationError("hopper residual must not be negative", residual=self.residual_kg)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "residual_kg": self.residual_kg, "released": self.released}


def hopper_state(*, residual_kg: float, released: bool) -> HopperState:
    """Record the hopper after a transfer."""

    return HopperState(residual_kg=round(residual_kg, 4), released=released)
