"""The recipe itself: factors per cubic metre and the mixing window."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..errors import ValidationError
from .grade import Grade


@dataclass(frozen=True, slots=True)
class Recipe:
    """A versioned formula for one grade."""

    name: str
    grade: Grade
    version: int
    factors: Mapping[str, float]
    mix_time_ticks: int
    moisture_ref_percent: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("recipe name must not be empty")
        if self.version < 0:
            raise ValidationError("recipe version must not be negative", name=self.name)
        if not self.factors:
            raise ValidationError("recipe needs at least one material factor", name=self.name)
        for material, factor in self.factors.items():
            if not material:
                raise ValidationError("recipe material name must not be empty", name=self.name)
            if factor <= 0:
                raise ValidationError(
                    "recipe factor must be positive", name=self.name, material=material, factor=factor
                )
        if self.mix_time_ticks < 1:
            raise ValidationError("recipe needs a positive mixing window", name=self.name)
        if not 0.0 <= self.moisture_ref_percent <= 100.0:
            raise ValidationError("recipe moisture reference must be a percentage", name=self.name)
        object.__setattr__(self, "factors", MappingProxyType(dict(self.factors)))

    @property
    def materials(self) -> tuple[str, ...]:
        return tuple(sorted(self.factors))

    def factor(self, material: str) -> float:
        """Return the factor of ``material`` or refuse the lookup."""

        value = self.factors.get(material)
        if value is None:
            raise ValidationError("recipe has no factor for this material", name=self.name, material=material)
        return value

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "grade": self.grade.describe(),
            "version": self.version,
            "factors": dict(self.factors),
            "mix_time_ticks": self.mix_time_ticks,
            "moisture_ref_percent": self.moisture_ref_percent,
        }

    def to_document(self) -> dict[str, Any]:
        document = self.describe()
        document["factors"] = dict(self.factors)
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Recipe":
        """Rebuild a recipe from a stored payload."""

        return cls(
            name=str(document["name"]),
            grade=Grade.from_document(document["grade"]),
            version=int(document["version"]),
            factors={str(material): float(value) for material, value in dict(document["factors"]).items()},
            mix_time_ticks=int(document["mix_time_ticks"]),
            moisture_ref_percent=float(document["moisture_ref_percent"]),
        )
