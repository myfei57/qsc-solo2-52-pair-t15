"""The production roll-up the shift report is built from."""

from __future__ import annotations

from typing import Any, Mapping

from ..decision.batch import BatchRegistry
from ..facts import flag


def production_summary(
    *,
    state: Mapping[str, Any],
    batches: BatchRegistry,
    alarms: int,
    samples: int,
    now: int,
) -> dict[str, Any]:
    """Fold the derived state into the numbers a shift report needs."""

    return {
        "tick": now,
        "batches": batches.count(),
        "weighed": flag(state, "agg.weigh"),
        "weight_persisted": flag(state, "agg.persist"),
        "dropped": flag(state, "agg.drop"),
        "mixed": flag(state, "mix.timer", key="finished"),
        "discharged": flag(state, "chute.door"),
        "pumped": flag(state, "pump.run"),
        "samples": samples,
        "alarms": alarms,
    }
