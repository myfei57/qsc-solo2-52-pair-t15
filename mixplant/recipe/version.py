"""Version stamps that make a stale recipe detectable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import StaleGenerationError
from .recipe import Recipe


@dataclass(frozen=True, slots=True)
class VersionStamp:
    """The recipe name and version a batching step was planned against."""

    name: str
    version: int

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}


def require_current(recipe: Recipe, current_version: int, *, action: str) -> None:
    """Refuse an action planned against an older recipe version."""

    if recipe.version != current_version:
        raise StaleGenerationError(
            "action was planned against an older recipe version",
            action=action,
            name=recipe.name,
            planned_version=recipe.version,
            current_version=current_version,
        )


def stamp_of(recipe: Recipe) -> VersionStamp:
    """Return the version stamp that belongs to ``recipe``."""

    return VersionStamp(name=recipe.name, version=recipe.version)


def describe_history(book_versions: tuple[Recipe, ...]) -> list[dict[str, Any]]:
    """Describe every version of one recipe, newest last."""

    return [recipe.describe() for recipe in book_versions]
