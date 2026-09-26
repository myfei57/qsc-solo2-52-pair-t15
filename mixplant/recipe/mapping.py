"""The bin-to-material mapping a batching plan is dispatched through."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import StaleGenerationError, ValidationError
from ..ns.topology import Topology
from .recipe import Recipe


@dataclass(frozen=True, slots=True)
class MaterialMapping:
    """Which bin holds which material, valid for one recipe version."""

    version: int
    assignments: Mapping[str, str]

    def bin_of(self, material: str) -> str:
        """Return the bin a material is loaded from."""

        bin_name = self.assignments.get(material)
        if bin_name is None:
            raise ValidationError("no bin is assigned to this material", material=material)
        return bin_name

    def describe(self) -> dict[str, Any]:
        return {"version": self.version, "assignments": dict(self.assignments)}


def build_mapping(recipe: Recipe, topology: Topology) -> MaterialMapping:
    """Resolve every recipe material to the bin that holds it."""

    assignments: dict[str, str] = {}
    for material in recipe.materials:
        assignments[material] = topology.source_for(material)
    return MaterialMapping(version=recipe.version, assignments=assignments)


def require_fresh(mapping: MaterialMapping, current_version: int, *, action: str) -> None:
    """Refuse when the mapping was built for an older recipe version."""

    if mapping.version != current_version:
        raise StaleGenerationError(
            "material mapping is older than the selected recipe",
            action=action,
            mapping_version=mapping.version,
            current_version=current_version,
        )
