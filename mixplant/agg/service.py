"""Aggregate service: weigh, persist, check, release and drop."""

from __future__ import annotations

from typing import Any

from ..context import SharedContext
from ..errors import ArtifactExpiredError, NotFoundError
from ..recipe.plan import plan_batch
from ..recipe.service import RecipeService
from ..recipe.batch import batch_payload
from ..service_base import PlantService
from ..statemachine.machine import SequenceMachine
from ..statemachine.phases import BatchPhase
from .agg import (
    BATCH_KIND,
    BIN_KIND,
    CALIBRATE_KIND,
    CHECK_KIND,
    DROP_KIND,
    HOPPER_KIND,
    PERSIST_KIND,
    RELEASE_KIND,
    REPORT_KIND,
    WEIGH_KIND,
    WET_MATERIALS,
)
from .bin import refresh
from .calibrate import calibrate
from .check import check_dry_weight
from .hopper import hopper_state
from .release import release_payload
from .report import summarise_reports, weight_report
from .summary import compose_status
from .weigh import reading_from_payload, weigh

class AggService(PlantService):
    """Batches the aggregates: it may not drop before the weight is durable."""

    origin = "agg"
    line = "batch"
    subject = "agg"

    def __init__(
        self,
        context: SharedContext,
        recipes: RecipeService,
        machine: SequenceMachine | None = None,
    ) -> None:
        super().__init__(context, machine)
        self.recipes = recipes
        self._calibration = calibrate(slope=1.0, offset=0.0)
        self._reports: list[dict[str, Any]] = []

    def declare_batch(self, *, batch_id: str, quantity: float) -> dict[str, Any]:
        """Declare the batch that the selected recipe is batched into."""

        if self.machine.is_at_least(BatchPhase.DROPPED.value):
            self.rewind(BatchPhase.IDLE.value, "previous batch finished, batching line reset")
        if self.machine.is_at(BatchPhase.IDLE.value):
            self.advance(BatchPhase.RECIPE_SELECTED.value, "batch declared against the selected recipe")
        recipe = self.recipes.current()
        plan = plan_batch(
            recipe,
            batch_id=batch_id,
            quantity=quantity,
            moisture_percent=recipe.moisture_ref_percent,
            wet_materials=WET_MATERIALS,
        )
        batch = self.context.batches.declare(
            batch_id,
            tick=self.context.clock.now(),
            generation=recipe.version,
            grade=recipe.grade.code,
            quantity=quantity,
        )
        self.publish(BATCH_KIND, batch_payload(plan))
        self.emit("agg.batch_declared", {**batch.describe(), "targets": plan.describe()["materials"]})
        return {"batch": batch.describe(), "batches": self.context.batches.count()}

    def map_bin(self, bin_name: str, material: str) -> dict[str, Any]:
        """Refresh the bin assignment for the selected recipe version."""

        self.require("agg.map_bin")
        self.recipes.require_current(action="agg.map_bin")
        state = refresh(bin_name, material, self.recipes.current_version())
        self.publish(BIN_KIND, state.describe())
        self.emit("agg.bin_mapped", {"bin": bin_name, "material": material})
        return {"bin": state.describe(), "mapping": self.recipes.mapping.describe()}

    def weigh(self, *, bin_name: str, actual_kg: float) -> dict[str, Any]:
        """Weigh one bin against its target for the current batch."""

        self.require("agg.weigh")
        self.recipes.require_current(action="agg.weigh")
        mapping = self.recipes.mapping
        material = self._material_of(bin_name, mapping.assignments)
        target = self._target_for(bin_name)
        reading = weigh(
            bin_name=bin_name,
            material=material,
            target_kg=target,
            actual_kg=self._calibration.apply(actual_kg) * self._scale_factor(),
            tolerance_percent=self.context.config.limits.scale_tolerance_percent,
        )
        self.publish(WEIGH_KIND, {**reading.describe(), "version": self.recipes.current_version()})
        if self.machine.is_at(BatchPhase.RECIPE_SELECTED.value):
            self.advance(BatchPhase.WEIGHING.value, "aggregate weighed against the selected recipe")
        self.emit("agg.weighed", reading.describe())
        if not reading.ok:
            self.raise_alarm("agg.weigh_out_of_tolerance", reading.describe())
        return {"weighing": reading.describe(), "targets": self._targets()}

    def persist(self) -> dict[str, Any]:
        """Write the weight durably so a restart keeps batching the same recipe."""

        self.require("agg.persist")
        reading = reading_from_payload(self.payload_entry("agg", "weigh"))
        record = self.publish(
            PERSIST_KIND,
            {
                "active": True,
                "version": self.recipes.current_version(),
                "material": reading.material,
                "actual_kg": reading.actual_kg,
            },
        )
        self.publish(
            REPORT_KIND,
            {
                "active": True,
                **weight_report(reading, batch_id=self._batch_id(), version=self.recipes.current_version()),
            },
        )
        self._reports.append(
            weight_report(reading, batch_id=self._batch_id(), version=self.recipes.current_version())
        )
        if self.machine.is_at(BatchPhase.WEIGHING.value):
            self.advance(BatchPhase.WEIGHED.value, "weight is durable")
        self.emit("agg.persisted", {"seq": record.seq, "version": self.recipes.current_version()})
        return {"persisted": record.seq, "report": summarise_reports(tuple(self._reports))}

    def check(self, *, actual_total_kg: float) -> dict[str, Any]:
        """Check the dry total; this must run after moisture compensation."""

        self.require("agg.check")
        plan = self._plan()
        verdict = check_dry_weight(
            materials=plan.materials,
            actual_kg=actual_total_kg,
            tolerance_percent=self.context.config.limits.scale_tolerance_percent,
            exclude=("water",),
        )
        self.publish(CHECK_KIND, {"active": True, **verdict.describe()})
        self.emit("agg.checked", verdict.describe())
        if not verdict.ok:
            self.raise_alarm("agg.dry_weight_out_of_tolerance", verdict.describe())
        return {"check": verdict.describe(), "plan": plan.describe()}

    def release(self, *, residual_kg: float) -> dict[str, Any]:
        """Empty the scale hopper before the mixer is stopped."""

        self.require("agg.release")
        payload = release_payload(
            residual_kg=residual_kg,
            threshold_kg=self.context.config.limits.hopper_residual_max_kg,
        )
        state = hopper_state(residual_kg=payload["residual_kg"], released=True)
        self.publish(HOPPER_KIND, {**state.describe(), "threshold_kg": payload["threshold_kg"]})
        self.publish(RELEASE_KIND, payload)
        self.emit("agg.hopper_released", payload)
        return {"release": payload}

    def drop(self) -> dict[str, Any]:
        """Drop the weighed material once the weight is durable."""

        self.require("agg.drop")
        record = self.publish(DROP_KIND, {"active": True, "version": self.recipes.current_version()})
        if self.machine.is_at(BatchPhase.WEIGHED.value):
            self.advance(BatchPhase.DROPPED.value, "weighed material dropped to the belt")
        self.emit("agg.dropped", {"seq": record.seq})
        return {"dropped": record.seq, "status": self.status()}

    def calibrate_scale(self, *, slope: float, offset: float) -> dict[str, Any]:
        """Re-calibrate the scale used for later weighings."""

        self._calibration = calibrate(slope=slope, offset=offset)
        self.publish(CALIBRATE_KIND, {"active": True, **self._calibration.describe()})
        baseline = self.context.versions.publish_baseline(
            "scale.factor",
            slope,
            "x",
            tick=self.context.clock.now(),
            ttl_ticks=self.context.config.defaults.baseline_ttl_ticks,
        )
        self.emit("agg.calibrated", self._calibration.describe())
        return {"calibration": self._calibration.describe(), "baseline": baseline.describe(self.context.clock.now())}

    def reports(self) -> dict[str, Any]:
        """Return every weight report kept for the current run."""

        return summarise_reports(tuple(self._reports))

    def status(self) -> dict[str, Any]:
        summary = compose_status(
            self.state(), now=self.context.clock.now(), limits=self.context.config.limits
        )
        summary["reports"] = self.reports()
        return summary

    def describe_targets(self) -> dict[str, Any]:
        """Describe the per bin targets of the current batch."""

        return self._targets()

    def reset(self) -> None:
        """Clear the per run reports after a rollback or a new run."""

        self._reports.clear()

    def _targets(self) -> dict[str, Any]:
        from .batch import targets_payload

        return targets_payload(self._plan(), self.recipes.mapping)

    def _plan(self):
        batch = self.context.batches.latest()
        if batch is None:
            raise NotFoundError("declare a batch before planning the aggregates")
        recipe = self.recipes.current()
        entry = self.payload_entry("moist", "comp")
        moisture = (
            float(entry.get("percent", recipe.moisture_ref_percent))
            if isinstance(entry, dict)
            else recipe.moisture_ref_percent
        )
        return plan_batch(
            recipe,
            batch_id=batch.batch_id,
            quantity=batch.quantity,
            moisture_percent=moisture,
            wet_materials=WET_MATERIALS,
        )

    def _target_for(self, bin_name: str) -> float:
        targets = self._targets()["targets"]
        target = targets.get(bin_name)
        if target is None:
            raise NotFoundError("the batch plan does not use this bin", bin=bin_name)
        return float(target)

    def _batch_id(self) -> str:
        batch = self.context.batches.latest()
        return "" if batch is None else batch.batch_id

    def _material_of(self, bin_name: str, assignments: Any) -> str:
        for material, assigned in assignments.items():
            if assigned == bin_name:
                return str(material)
        raise NotFoundError("no material is mapped to this bin", bin=bin_name)

    def _scale_factor(self) -> float:
        """Return the published scale factor, or one when none is in force."""

        if self.context.versions.latest_baseline("scale.factor") is None:
            return 1.0
        try:
            return self.context.versions.baseline_value(
                "scale.factor", now=self.context.clock.now()
            )
        except ArtifactExpiredError:
            self.raise_alarm("agg.baseline_expired", {"name": "scale.factor"})
            return 1.0
