"""Per material moisture references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import NotFoundError, ValidationError

DEFAULT_REFERENCES: Mapping[str, float] = {
    "sand": 4.5,
    "gravel": 1.2,
    "cement": 0.0,
    "fly-ash": 0.3,
    "admixture": 0.0,
    "water": 0.0,
}


@dataclass(frozen=True, slots=True)
class MoistureTable:
    """Reference moisture per material, overridable per station."""

    references: Mapping[str, float]

    def __post_init__(self) -> None:
        for material, percent in self.references.items():
            if not material:
                raise ValidationError("moisture table material must not be empty")
            if percent < 0.0:
                raise ValidationError(
                    "moisture reference must not be negative", material=material, percent=percent
                )

    def reference(self, material: str) -> float:
        """Return the reference moisture of ``material``."""

        value = self.references.get(material)
        if value is None:
            raise NotFoundError("material has no moisture reference", material=material)
        return value

    def describe(self) -> dict[str, Any]:
        return {"references": dict(sorted(self.references.items()))}


def default_table() -> MoistureTable:
    """Return the reference table the station ships with."""

    return MoistureTable(references=dict(DEFAULT_REFERENCES))
