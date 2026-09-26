"""One cement or fly ash silo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class SiloState:
    """How much material a silo currently holds."""

    name: str
    material: str
    level_kg: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("silo name must not be empty")
        if self.level_kg < 0:
            raise ValidationError("silo level must not be negative", silo=self.name)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "silo": self.name, "material": self.material, "level_kg": self.level_kg}


def silo_state(name: str, material: str, level_kg: float) -> SiloState:
    """Build the state of one silo."""

    return SiloState(name=name, material=material, level_kg=round(level_kg, 4))
