"""Free water and the aggregate mass it adds back."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class Compensation:
    """The correction one wet material contributes to a batch."""

    material: str
    dry_mass: float
    moisture_percent: float
    free_water_l: float
    wet_mass: float

    def describe(self) -> dict[str, Any]:
        return {
            "material": self.material,
            "dry_mass": self.dry_mass,
            "moisture_percent": self.moisture_percent,
            "free_water_l": self.free_water_l,
            "wet_mass": self.wet_mass,
        }


def require_percent(moisture_percent: float) -> float:
    """Return a usable percentage or refuse the call."""

    if not 0.0 <= moisture_percent <= 100.0:
        raise ValidationError("moisture must be a percentage", moisture_percent=moisture_percent)
    return moisture_percent


def free_water(dry_mass: float, moisture_percent: float) -> float:
    """Return the litres of free water carried by ``dry_mass``."""

    return round(require_percent(moisture_percent) / 100.0 * dry_mass, 4)


def compensated_mass(dry_mass: float, moisture_percent: float) -> float:
    """Return the wet mass the scale has to weigh out."""

    return round(dry_mass + free_water(dry_mass, moisture_percent), 4)


def compensate(material: str, dry_mass: float, moisture_percent: float) -> Compensation:
    """Build the compensation record for one wet material."""

    return Compensation(
        material=material,
        dry_mass=round(dry_mass, 4),
        moisture_percent=require_percent(moisture_percent),
        free_water_l=free_water(dry_mass, moisture_percent),
        wet_mass=compensated_mass(dry_mass, moisture_percent),
    )


def water_offset(compensations: tuple[Compensation, ...]) -> float:
    """Return how much batching water the compensations already supplied."""

    return round(sum(item.free_water_l for item in compensations), 4)
