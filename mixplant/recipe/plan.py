"""Turning a recipe and a batch size into material quantities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import ValidationError
from .recipe import Recipe


@dataclass(frozen=True, slots=True)
class BatchPlan:
    """The masses one batch needs, already moisture compensated."""

    batch_id: str
    grade: str
    version: int
    quantity: float
    unit: str
    materials: Mapping[str, float]
    free_water_l: float
    moisture_percent: float

    def material_mass(self, material: str) -> float:
        """Return the compensated mass of ``material``."""

        value = self.materials.get(material)
        if value is None:
            raise ValidationError("batch plan has no mass for this material", material=material)
        return value

    @property
    def dry_total(self) -> float:
        return round(sum(self.materials.values()), 4)

    def describe(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "grade": self.grade,
            "version": self.version,
            "quantity": self.quantity,
            "unit": self.unit,
            "materials": dict(self.materials),
            "dry_total": self.dry_total,
            "free_water_l": self.free_water_l,
            "moisture_percent": self.moisture_percent,
        }


def plan_batch(
    recipe: Recipe,
    *,
    batch_id: str,
    quantity: float,
    moisture_percent: float = 0.0,
    wet_materials: tuple[str, ...] = ("sand",),
) -> BatchPlan:
    """Scale every factor to ``quantity`` and add back the aggregate water."""

    if not batch_id:
        raise ValidationError("batch identity must not be empty")
    if quantity <= 0:
        raise ValidationError("batch quantity must be positive", quantity=quantity)
    if not 0.0 <= moisture_percent <= 100.0:
        raise ValidationError("moisture must be a percentage", moisture_percent=moisture_percent)
    materials: dict[str, float] = {}
    free_water = 0.0
    for material, factor in recipe.factors.items():
        dry = factor * quantity
        if material in wet_materials and moisture_percent > 0:
            water = dry * moisture_percent / 100.0
            free_water += water
            dry += water
        materials[material] = round(dry, 4)
    return BatchPlan(
        batch_id=batch_id,
        grade=recipe.grade.code,
        version=recipe.version,
        quantity=quantity,
        unit="m3",
        materials=materials,
        free_water_l=round(free_water, 4),
        moisture_percent=moisture_percent,
    )
