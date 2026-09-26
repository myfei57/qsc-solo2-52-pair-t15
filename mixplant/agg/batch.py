"""Turning a batch plan and a mapping into per bin targets."""

from __future__ import annotations

from typing import Any, Mapping

from ..errors import ValidationError
from ..recipe.mapping import MaterialMapping
from ..recipe.plan import BatchPlan


def bin_targets(plan: BatchPlan, mapping: MaterialMapping) -> dict[str, float]:
    """Return the mass every bin has to weigh out for ``plan``."""

    targets: dict[str, float] = {}
    for material, mass in plan.materials.items():
        bin_name = mapping.bin_of(material)
        targets[bin_name] = round(targets.get(bin_name, 0.0) + mass, 4)
    return targets


def targets_payload(plan: BatchPlan, mapping: MaterialMapping) -> dict[str, Any]:
    """Describe the bin targets the batching page shows."""

    targets = bin_targets(plan, mapping)
    if not targets:
        raise ValidationError("batch plan produced no bin targets", batch_id=plan.batch_id)
    return {
        "batch_id": plan.batch_id,
        "version": plan.version,
        "targets": targets,
        "total_kg": round(sum(targets.values()), 4),
    }


def scale_out(reading_payload: Mapping[str, Any] | None, tolerance: float) -> dict[str, Any]:
    """Summarise the weighing the batching page renders."""

    if not reading_payload:
        return {"weighed": False, "ok": None, "deviation_percent": None, "tolerance_percent": tolerance}
    return {
        "weighed": True,
        "bin": reading_payload.get("bin"),
        "material": reading_payload.get("material"),
        "target_kg": reading_payload.get("target_kg"),
        "actual_kg": reading_payload.get("actual_kg"),
        "deviation_percent": reading_payload.get("deviation_percent"),
        "ok": reading_payload.get("ok"),
        "tolerance_percent": tolerance,
    }
