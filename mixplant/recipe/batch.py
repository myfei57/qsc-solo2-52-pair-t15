"""The record body a declared batch is stored under."""

from __future__ import annotations

from typing import Any

from .plan import BatchPlan


def batch_payload(plan: BatchPlan) -> dict[str, Any]:
    """Build the payload a declared batch is written with."""

    return {
        "active": True,
        "batch_id": plan.batch_id,
        "grade": plan.grade,
        "version": plan.version,
        "generation": plan.version,
        "quantity": plan.quantity,
        "unit": plan.unit,
        "materials": dict(plan.materials),
        "free_water_l": plan.free_water_l,
    }


def plan_summary(plan: BatchPlan) -> dict[str, Any]:
    """Summarise a plan for the batching page."""

    return {
        "batch_id": plan.batch_id,
        "grade": plan.grade,
        "version": plan.version,
        "materials": {material: plan.material_mass(material) for material in sorted(plan.materials)},
        "dry_total": plan.dry_total,
        "free_water_l": plan.free_water_l,
    }
