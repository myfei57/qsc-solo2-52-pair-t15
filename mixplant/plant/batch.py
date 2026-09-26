"""Read model behind the batching page."""

from __future__ import annotations

from typing import Any, Mapping

from ..recipe.batch import plan_summary


def batch_view(*, recipe_service: Any, agg_service: Any, moist_service: Any, config: Mapping[str, Any]) -> dict[str, Any]:
    """Build the batching view, including the per bin targets."""

    batch = agg_service.context.batches.latest()
    payload: dict[str, Any] = {
        "batch": None if batch is None else batch.describe(),
        "recipe": recipe_service.status(),
        "aggregate": agg_service.status(),
        "moisture": moist_service.status(),
        "config": dict(config),
        "targets": None,
        "plan": None,
    }
    if batch is not None and recipe_service.mapping_or_none() is not None:
        payload["targets"] = agg_service.describe_targets()
        payload["plan"] = plan_summary(_plan(recipe_service, batch.batch_id, batch.quantity, moist_service))
    return payload


def _plan(recipe_service: Any, batch_id: str, quantity: float, moist_service: Any):
    """Rebuild the plan the batch page shows."""

    from ..recipe.plan import plan_batch

    recipe = recipe_service.current()
    percent = moist_service.compensations[-1].moisture_percent if moist_service.compensations else recipe.moisture_ref_percent
    return plan_batch(recipe, batch_id=batch_id, quantity=quantity, moisture_percent=percent)
