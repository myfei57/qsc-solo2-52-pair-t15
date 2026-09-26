"""Moisture service: it must compensate before the dry weight is checked."""

from __future__ import annotations

from typing import Any

from ..context import SharedContext
from ..recipe.book import RecipeBook
from ..recipe.plan import plan_batch
from ..service_base import PlantService
from ..statemachine.machine import SequenceMachine
from .comp import Compensation, compensate, water_offset
from .mode import mode_for
from .table import MoistureTable

COMP_KIND = "moist.comp"
MODE_KIND = "moist.mode"


class MoistService(PlantService):
    """Records the aggregate moisture and the mass it adds back."""

    origin = "moist"
    line = "batch"
    subject = "moist"

    def __init__(
        self,
        context: SharedContext,
        book: RecipeBook,
        table: MoistureTable,
        machine: SequenceMachine | None = None,
    ) -> None:
        super().__init__(context, machine)
        self.book = book
        self.table = table
        self._compensations: list[Compensation] = []

    def compensate(self, *, material: str, moisture_percent: float, quantity: float) -> dict[str, Any]:
        """Apply the moisture correction for ``material``."""

        self.require_order(quantity > 0, "a compensation needs a positive batch size", quantity=quantity)
        recipe = self.book.selected()
        correction = compensate(material, recipe.factor(material) * quantity, moisture_percent)
        mode = mode_for(moisture_percent, self.context.config.limits)
        self._compensations.append(correction)
        self.publish(
            MODE_KIND,
            {"active": True, "mode": str(mode.value), "material": material, "percent": moisture_percent},
        )
        record = self.publish(
            COMP_KIND,
            {"active": True, **correction.describe(), "batch_quantity": quantity, "version": recipe.version},
        )
        self.emit("moist.compensated", {"material": material, "free_water_l": correction.free_water_l})
        return {
            "compensation": correction.describe(),
            "mode": str(mode.value),
            "table_reference": self.table.reference(material),
            "seq": record.seq,
        }

    @property
    def compensations(self) -> tuple[Compensation, ...]:
        return tuple(self._compensations)

    def water_offset(self) -> float:
        """Return the free water the compensations already supplied."""

        return water_offset(self.compensations)

    def plan(self, batch_id: str, quantity: float) -> dict[str, Any]:
        """Plan a batch with the moisture currently on the aggregates."""

        recipe = self.book.selected()
        percent = self.compensations[-1].moisture_percent if self._compensations else recipe.moisture_ref_percent
        return plan_batch(recipe, batch_id=batch_id, quantity=quantity, moisture_percent=percent).describe()

    def sync(self, corrections: list[Compensation]) -> None:
        """Adopt compensations rebuilt from the stream after a restart."""

        self._compensations = list(corrections)

    def status(self) -> dict[str, Any]:
        entry = self.payload_entry("moist", "comp")
        return {
            "compensated": entry is not None,
            "material": entry.get("material") if entry else None,
            "percent": float(entry.get("percent", 0.0)) if entry else None,
            "free_water_l": round(self.water_offset(), 4),
            "mode": (self.payload_entry("moist", "mode") or {}).get("mode"),
        }
