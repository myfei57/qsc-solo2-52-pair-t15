"""Fact names and the derivation used by gates and interlocks.

Services write facts into the record stream; the gate layer only ever reads
them from the derived state.  Keeping the translation in one place means a
restart rebuilds exactly the same facts as a live process.
"""

from __future__ import annotations

from typing import Any, Mapping

RECIPE_PUBLISHED = "recipe.published"
RECIPE_SELECTED = "recipe.selected"
BIN_MAPPED = "agg.bin_mapped"
WEIGHT_PERSISTED = "agg.weight_persisted"
AGG_DROPPED = "agg.dropped"
HOPPER_RELEASED = "agg.hopper_released"
CEMENT_GATE_OPEN = "cement.gate_open"
CEMENT_FED = "cement.fed"
WATER_DISPENSED = "water.dispensed"
WATER_PRIMED = "water.primed"
MIXER_RUNNING = "mix.running"
MIX_TIMED = "mix.timed"
CHUTE_OPEN = "chute.door_open"
TRUCK_LOADED = "chute.loaded"
PUMP_RUNNING = "pump.running"
SAMPLER_LATCHED = "sampler.latched"
MOIST_COMPENSATED = "moist.compensated"


def flag(state: Mapping[str, Any], path: str, key: str = "active") -> bool:
    """Read a boolean leaf such as ``agg.persist`` out of derived state."""

    group, _, leaf = path.partition(".")
    node = state.get(group)
    if not isinstance(node, Mapping):
        return False
    entry = node.get(leaf)
    if not isinstance(entry, Mapping):
        return False
    return bool(entry.get(key, False))


def _latch(state: Mapping[str, Any], group: str) -> bool:
    node = state.get(group)
    if not isinstance(node, Mapping):
        return False
    entry = node.get("latch")
    return bool(entry.get("active", False)) if isinstance(entry, Mapping) else False


def derive_facts(state: Mapping[str, Any]) -> dict[str, bool]:
    """Translate derived state into the boolean facts gates evaluate."""

    return {
        RECIPE_PUBLISHED: flag(state, "recipe.published"),
        RECIPE_SELECTED: flag(state, "recipe.selected"),
        BIN_MAPPED: flag(state, "agg.bin"),
        WEIGHT_PERSISTED: flag(state, "agg.persist"),
        AGG_DROPPED: flag(state, "agg.drop"),
        HOPPER_RELEASED: flag(state, "agg.release"),
        CEMENT_GATE_OPEN: flag(state, "cement.gate"),
        CEMENT_FED: flag(state, "cement.flow"),
        WATER_DISPENSED: flag(state, "water.dispense"),
        WATER_PRIMED: flag(state, "water.prime"),
        MIXER_RUNNING: flag(state, "mix.mixer"),
        MIX_TIMED: flag(state, "mix.timer", key="finished"),
        CHUTE_OPEN: flag(state, "chute.door"),
        TRUCK_LOADED: flag(state, "chute.load"),
        PUMP_RUNNING: flag(state, "pump.run"),
        SAMPLER_LATCHED: _latch(state, "sampler"),
        MOIST_COMPENSATED: flag(state, "moist.comp"),
    }
