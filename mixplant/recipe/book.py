"""The book that keeps published recipes and the selected one."""

from __future__ import annotations

from typing import Any

from ..errors import DuplicateError, NotFoundError, ValidationError
from .recipe import Recipe


class RecipeBook:
    """Stores every published version and remembers which one is selected."""

    __slots__ = ("_versions", "_selected")

    def __init__(self) -> None:
        self._versions: dict[str, list[Recipe]] = {}
        self._selected: str | None = None

    def publish(self, recipe: Recipe) -> Recipe:
        """Store a new version; the same name and version may not repeat."""

        history = self._versions.setdefault(recipe.name, [])
        if any(existing.version == recipe.version for existing in history):
            raise DuplicateError(
                "recipe version was published twice", name=recipe.name, version=recipe.version
            )
        history.append(recipe)
        return recipe

    def adopt(self, recipe: Recipe) -> Recipe:
        """Adopt a recipe read back from the stream after a restart."""

        history = self._versions.setdefault(recipe.name, [])
        if not any(existing.version == recipe.version for existing in history):
            history.append(recipe)
        return recipe

    def select(self, name: str) -> Recipe:
        """Select the newest version of ``name``."""

        recipe = self.current(name)
        self._selected = name
        return recipe

    def selected(self) -> Recipe:
        """Return the selected recipe or refuse the call."""

        if self._selected is None:
            raise NotFoundError("no recipe has been selected")
        return self.current(self._selected)

    def selected_name(self) -> str | None:
        return self._selected

    def current(self, name: str) -> Recipe:
        """Return the newest published version of ``name``."""

        history = self._versions.get(name)
        if not history:
            raise NotFoundError("recipe was never published", name=name)
        return history[-1]

    def version(self, name: str, version: int) -> Recipe:
        """Return one exact published version."""

        history = self._versions.get(name, [])
        for recipe in history:
            if recipe.version == version:
                return recipe
        raise NotFoundError("recipe version was never published", name=name, version=version)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._versions))

    def history(self, name: str) -> tuple[Recipe, ...]:
        if not name:
            raise ValidationError("recipe name must not be empty")
        return tuple(self._versions.get(name, ()))

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "selected": name == self._selected,
                "versions": [recipe.version for recipe in self._versions[name]],
                "current": self._versions[name][-1].describe(),
            }
            for name in self.names()
        ]
