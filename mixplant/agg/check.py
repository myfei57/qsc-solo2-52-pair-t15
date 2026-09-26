"""The dry weight check that must follow moisture compensation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import ValidationError
from .scale import deviation_percent, within_tolerance


@dataclass(frozen=True, slots=True)
class DryWeightCheck:
    """The planned total against the total the scale actually reported."""

    planned_kg: float
    actual_kg: float
    deviation_percent: float
    tolerance_percent: float
    ok: bool

    def describe(self) -> dict[str, Any]:
        return {
            "planned_kg": self.planned_kg,
            "actual_kg": self.actual_kg,
            "deviation_percent": self.deviation_percent,
            "tolerance_percent": self.tolerance_percent,
            "ok": self.ok,
        }


def planned_total(materials: Mapping[str, float], *, exclude: tuple[str, ...] = ()) -> float:
    """Return the planned mass of every material except ``exclude``."""

    return round(sum(mass for material, mass in materials.items() if material not in exclude), 4)


def check_dry_weight(
    *,
    materials: Mapping[str, float],
    actual_kg: float,
    tolerance_percent: float,
    exclude: tuple[str, ...] = (),
) -> DryWeightCheck:
    """Compare the planned dry total with the reported total."""

    planned = planned_total(materials, exclude=exclude)
    if planned <= 0:
        raise ValidationError("dry weight check needs a positive planned total", planned_kg=planned)
    deviation = deviation_percent(actual_kg, planned)
    return DryWeightCheck(
        planned_kg=planned,
        actual_kg=round(actual_kg, 4),
        deviation_percent=deviation,
        tolerance_percent=tolerance_percent,
        ok=within_tolerance(deviation, tolerance_percent),
    )
