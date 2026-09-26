"""Drawdown accounting for the cement silos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class Inventory:
    """The level of every silo the plant knows about."""

    levels: Mapping[str, float]

    def level(self, silo: str) -> float:
        value = self.levels.get(silo)
        if value is None:
            raise NotFoundError("silo has no inventory record", silo=silo)
        return value

    def describe(self) -> dict[str, Any]:
        return {"levels": dict(sorted(self.levels.items()))}


class InventoryLedger:
    """Applies deliveries and drawdowns to the silo levels."""

    __slots__ = ("_levels",)

    def __init__(self, opening: Mapping[str, float] | None = None) -> None:
        self._levels: dict[str, float] = dict(opening or {})

    def deliver(self, silo: str, kg: float) -> float:
        """Add a delivery to ``silo`` and return the new level."""

        if kg <= 0:
            raise ValidationError("a delivery must be positive", silo=silo, kg=kg)
        return self._set(silo, self._levels.get(silo, 0.0) + kg)

    def draw(self, silo: str, kg: float) -> float:
        """Remove a drawdown from ``silo`` and return the new level."""

        if kg <= 0:
            raise ValidationError("a drawdown must be positive", silo=silo, kg=kg)
        level = self._levels.get(silo, 0.0) - kg
        if level < 0:
            raise ValidationError("drawdown would push the silo below zero", silo=silo, kg=kg)
        return self._set(silo, level)

    def levels(self) -> Inventory:
        return Inventory(levels=dict(self._levels))

    def _set(self, silo: str, level: float) -> float:
        rounded = round(level, 4)
        self._levels[silo] = rounded
        return rounded
