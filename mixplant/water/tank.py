"""The batching water tank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class TankState:
    """How much water the tank holds."""

    name: str
    level_l: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("tank name must not be empty")
        if self.level_l < 0:
            raise ValidationError("tank level must not be negative", tank=self.name)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "tank": self.name, "level_l": self.level_l}


def tank_state(name: str, level_l: float) -> TankState:
    """Build the state of the water tank."""

    return TankState(name=name, level_l=round(level_l, 4))
