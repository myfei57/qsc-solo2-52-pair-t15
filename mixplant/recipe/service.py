"""Recipe service: publishing, selecting and mapping a formula."""

from __future__ import annotations

from typing import Any, Mapping

from ..context import SharedContext
from ..errors import NotFoundError
from ..ns.topology import Topology
from ..service_base import PlantService
from ..statemachine.machine import SequenceMachine
from ..statemachine.phases import BatchPhase
from .book import RecipeBook
from .grade import grade_for
from .mapping import MaterialMapping, build_mapping, require_fresh
from .recipe import Recipe
from .validate import require_valid, validate_recipe
from .version import describe_history, stamp_of

PUBLISHED_KIND = "recipe.published"
SELECTED_KIND = "recipe.selected"
VERSION_KIND = "recipe.version"

SUBJECT = "recipe"


class RecipeService(PlantService):
    """Owns the recipe book and the mapping batching is dispatched through."""

    origin = "recipe"
    line = "batch"
    subject = SUBJECT

    def __init__(
        self,
        context: SharedContext,
        topology: Topology,
        machine: SequenceMachine | None = None,
    ) -> None:
        super().__init__(context, machine)
        self.book = RecipeBook()
        self.topology = topology
        self._mapping: MaterialMapping | None = None

    def publish_recipe(
        self,
        *,
        name: str,
        grade_code: str,
        factors: Mapping[str, float],
        mix_time_ticks: int | None = None,
        moisture_ref_percent: float | None = None,
    ) -> dict[str, Any]:
        """Validate and publish a new version of ``name``."""

        token = self.context.versions.bump(SUBJECT, tick=self.context.clock.now())
        recipe = Recipe(
            name=name,
            grade=grade_for(grade_code),
            version=token.value,
            factors=dict(factors),
            mix_time_ticks=(
                self.context.config.limits.mix_time_ticks if mix_time_ticks is None else mix_time_ticks
            ),
            moisture_ref_percent=(
                self.context.config.limits.moisture_max_percent / 2.0
                if moisture_ref_percent is None
                else moisture_ref_percent
            ),
        )
        require_valid(validate_recipe(recipe, self.context.config.limits))
        self.book.publish(recipe)
        self.publish(PUBLISHED_KIND, {"active": True, **recipe.describe()})
        self.publish(VERSION_KIND, {"active": True, "name": recipe.name, "version": recipe.version})
        self.emit("recipe.published", {"name": recipe.name, "version": recipe.version})
        return {"recipe": recipe.describe(), "generation": token.describe()}

    def select(self, name: str) -> dict[str, Any]:
        """Select ``name`` and rebuild the material mapping for its version."""

        self.require("recipe.select")
        recipe = self.book.select(name)
        self._mapping = build_mapping(recipe, self.topology)
        self.publish(
            SELECTED_KIND,
            {"active": True, "name": recipe.name, "version": recipe.version, "stamp": stamp_of(recipe).describe()},
        )
        if self.machine.is_at(BatchPhase.IDLE.value):
            self.advance(BatchPhase.RECIPE_SELECTED.value, "recipe selected for the next batch")
        self.emit("recipe.selected", {"name": recipe.name, "version": recipe.version})
        return {"recipe": recipe.describe(), "mapping": self._mapping.describe()}

    def current(self) -> Recipe:
        """Return the selected recipe."""

        return self.book.selected()

    def current_version(self) -> int:
        return self.book.selected().version

    @property
    def mapping(self) -> MaterialMapping:
        """Return the mapping for the selected version or refuse the call."""

        if self._mapping is None:
            raise NotFoundError("no material mapping has been built yet")
        return self._mapping

    def mapping_or_none(self) -> MaterialMapping | None:
        """Return the mapping when one exists, without raising."""

        return self._mapping

    def require_current(self, *, action: str) -> None:
        """Refuse an action planned against an older recipe version."""

        require_fresh(self.mapping, self.current_version(), action=action)

    def adopt(self, recipe: Recipe, *, selected: bool) -> None:
        """Adopt a recipe read back from the stream after a restart."""

        self.context.versions.generations.adopt(SUBJECT, recipe.version)
        self.book.adopt(recipe)
        if selected:
            self.book.select(recipe.name)
            self._mapping = build_mapping(recipe, self.topology)

    def history(self, name: str) -> list[dict[str, Any]]:
        return describe_history(self.book.history(name))

    def status(self) -> dict[str, Any]:
        selected = self.book.selected_name()
        return {
            "selected": selected,
            "version": None if selected is None else self.current_version(),
            "recipes": self.book.names(),
            "mapping": None if self._mapping is None else self._mapping.describe(),
            "phase": self.machine.phase,
        }
