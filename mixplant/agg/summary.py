"""Read model for the aggregate side of the plant."""

from __future__ import annotations

from typing import Any, Mapping

from ..config import Limits
from .batch import scale_out
from .release import describe_release


def compose_status(state: Mapping[str, Any], *, now: int, limits: Limits) -> dict[str, Any]:
    """Summarise the aggregate subsystem from derived state."""

    group = state.get("agg") if isinstance(state, Mapping) else None
    agg = group if isinstance(group, Mapping) else {}
    weight = agg.get("weigh") if isinstance(agg.get("weigh"), Mapping) else None
    persist = agg.get("persist") if isinstance(agg.get("persist"), Mapping) else None
    drop = agg.get("drop") if isinstance(agg.get("drop"), Mapping) else None
    bin_entry = agg.get("bin") if isinstance(agg.get("bin"), Mapping) else None
    hopper = agg.get("hopper") if isinstance(agg.get("hopper"), Mapping) else None
    check = agg.get("check") if isinstance(agg.get("check"), Mapping) else None
    return {
        "now": now,
        "weigh": scale_out(weight, limits.scale_tolerance_percent),
        "persisted": persist is not None,
        "persisted_version": None if persist is None else persist.get("version"),
        "dropped": drop is not None,
        "bin": None if bin_entry is None else bin_entry.get("bin"),
        "material": None if bin_entry is None else bin_entry.get("material"),
        "check": None if check is None else dict(check),
        "release": describe_release(agg.get("release")),
        "hopper_residual_kg": None if hopper is None else hopper.get("residual_kg"),
        "tolerance_percent": limits.scale_tolerance_percent,
    }
