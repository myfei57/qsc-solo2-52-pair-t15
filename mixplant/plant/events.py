"""The catalogue of domain events the plant emits."""

from __future__ import annotations

from typing import Any, Mapping

EVENT_NAMES: Mapping[str, str] = {
    "recipe.published": "recipe",
    "recipe.selected": "recipe",
    "agg.bin_mapped": "agg",
    "agg.weighed": "agg",
    "agg.persisted": "agg",
    "agg.checked": "agg",
    "agg.dropped": "agg",
    "agg.hopper_released": "agg",
    "cement.gate_opened": "cement",
    "cement.fed": "cement",
    "water.valve_opened": "water",
    "water.dispensed": "water",
    "water.primed": "water",
    "mix.started": "mix",
    "mix.fed": "mix",
    "mix.window_started": "mix",
    "mix.window_finished": "mix",
    "mix.sample_scheduled": "mix",
    "mix.stopped": "mix",
    "chute.truck_queued": "chute",
    "chute.door_opened": "chute",
    "chute.loaded": "chute",
    "chute.confirmed": "chute",
    "chute.door_closed": "chute",
    "pump.started": "pump",
    "pump.stroke": "pump",
    "pump.pressure": "pump",
    "pump.finished": "pump",
    "sampler.drawn": "sampler",
    "sampler.released": "sampler",
    "sampler.filed": "sampler",
}


def events_for(origin: str) -> tuple[str, ...]:
    """Return every event name that belongs to ``origin``."""

    return tuple(name for name, source in EVENT_NAMES.items() if source == origin)


def origins() -> tuple[str, ...]:
    """Return every origin that emits at least one event."""

    seen: list[str] = []
    for source in EVENT_NAMES.values():
        if source not in seen:
            seen.append(source)
    return tuple(seen)


def catalogue() -> list[dict[str, Any]]:
    """Describe every event the plant can emit."""

    return [{"name": name, "origin": EVENT_NAMES[name]} for name in sorted(EVENT_NAMES)]
