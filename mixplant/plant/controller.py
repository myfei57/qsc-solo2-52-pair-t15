"""The console controller: one place that builds every page model."""

from __future__ import annotations

from typing import Any, Mapping

from .batch import batch_view
from .diagnostics import run_diagnostics
from .manifest import describe_manifest
from .mix import mix_view
from .recipe import recipe_view
from .truck import truck_view


class PlantController:
    """Wraps the runtime and turns it into the documents the pages render."""

    __slots__ = ("runtime",)

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def recipe_view(self) -> dict[str, Any]:
        return recipe_view(self.runtime.recipes)

    def batch_view(self) -> dict[str, Any]:
        return batch_view(
            recipe_service=self.runtime.recipes,
            agg_service=self.runtime.agg,
            moist_service=self.runtime.moist,
            config=self.runtime.config.describe(),
        )

    def mix_view(self) -> dict[str, Any]:
        return mix_view(
            mix_service=self.runtime.mix,
            cement_service=self.runtime.cement,
            water_service=self.runtime.water,
        )

    def discharge_view(self) -> dict[str, Any]:
        return truck_view(
            chute_service=self.runtime.chute,
            pump_service=self.runtime.pump,
            sampler_service=self.runtime.sampler,
        )

    def alarm_view(self) -> dict[str, Any]:
        return {
            "alarms": self.runtime.alarms.recent(),
            "audit": self.runtime.audit.recent(),
            "counts": self.runtime.audit.counts(),
        }

    def manifest(self) -> dict[str, Any]:
        return describe_manifest(
            station=self.runtime.config.station,
            topology=self.runtime.topology,
            registry=self.runtime.registry,
            record_kinds=sorted({record.kind for record in self.runtime.store.visible()}),
            machines=self.runtime.machines,
        )

    def diagnostics(self) -> dict[str, Any]:
        rules = self.runtime.engine.rules()
        return run_diagnostics(
            rule_names=[rule.name for rule in rules],
            rule_actions=[rule.action for rule in rules],
            machines=self.runtime.machines,
            watermark=self.runtime.store.watermark().describe(),
        )

    def health(self) -> Mapping[str, Any]:
        return self.runtime.health()
