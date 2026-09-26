"""Helpers that drive a complete production cycle."""

from __future__ import annotations

from typing import Any

from mixplant.runtime import PlantRuntime

RECIPE = {
    "name": "mix-a",
    "grade": "C30",
    "factors": {"sand": 760.0, "gravel": 1010.0, "cement": 330.0, "water": 175.0},
    "moisture_ref_percent": 4.5,
}


def run(runtime: PlantRuntime, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch one command and return the result."""

    return runtime.dispatch(command, payload or {})["result"]


def publish_and_select(runtime: PlantRuntime) -> None:
    run(runtime, "recipe.publish", dict(RECIPE))
    run(runtime, "recipe.select", {"name": RECIPE["name"]})


def batch_and_weigh(runtime: PlantRuntime, *, batch_id: str = "B-001", quantity: float = 6.0) -> None:
    publish_and_select(runtime)
    run(runtime, "batch.declare", {"batch_id": batch_id, "quantity": quantity})
    run(runtime, "agg.map_bin", {"bin": "bin-1", "material": "sand"})
    run(runtime, "moist.compensate", {"material": "sand", "moisture_percent": 4.5, "quantity": quantity})
    targets = runtime.agg.describe_targets()["targets"]
    for bin_name in sorted(targets):
        if bin_name.startswith("bin-"):
            run(runtime, "agg.weigh", {"bin": bin_name, "actual_kg": targets[bin_name]})
    run(runtime, "agg.persist")


def start_mixer(runtime: PlantRuntime, *, batch_id: str = "B-001") -> None:
    """Drive a weighed batch onto a running mixer."""

    batch_and_weigh(runtime, batch_id=batch_id)
    run(runtime, "agg.check", {"actual_total_kg": runtime.agg.describe_targets()["total_kg"] - 1050.0})
    run(runtime, "agg.drop")
    run(runtime, "mix.start")


def advance_to_mixing(runtime: PlantRuntime, *, batch_id: str = "B-001") -> None:
    """Feed both inputs and start the mixing window."""

    start_mixer(runtime, batch_id=batch_id)
    run(runtime, "agg.release", {"residual_kg": 3.0})
    run(runtime, "cement.load_silo", {"silo": "silo-1", "material": "cement", "level_kg": 60000})
    run(runtime, "water.open_valve", {"target_l": 1050})
    run(runtime, "water.dispense", {"litres": 1050, "rate_lps": 45})
    run(runtime, "mix.feed", {"component": "water"})
    run(runtime, "cement.open_gate", {"silo": "silo-1", "target_kg": 1980})
    run(runtime, "cement.close_gate", {"silo": "silo-1", "mass_kg": 1980, "rate_kgs": 30})
    run(runtime, "mix.feed", {"component": "cement"})
    run(runtime, "mix.time")


def advance_to_mixed(runtime: PlantRuntime, *, batch_id: str = "B-001") -> None:
    """Close the mixing window so the batch is ready to discharge."""

    advance_to_mixing(runtime, batch_id=batch_id)
    run(runtime, "clock.advance", {"ticks": 8})
    run(runtime, "mix.finish")


def run_full_cycle(runtime: PlantRuntime, *, batch_id: str = "B-001", truck_id: str = "T-01") -> None:
    """Drive one batch from recipe to filed sample."""

    advance_to_mixed(runtime, batch_id=batch_id)
    run(runtime, "mix.schedule")
    run(runtime, "chute.arrive", {"truck_id": truck_id})
    run(runtime, "chute.open")
    run(runtime, "chute.load", {"truck_id": truck_id, "volume_m3": 6})
    run(runtime, "chute.confirm", {"truck_id": truck_id, "volume_m3": 6})
    run(runtime, "chute.close")
    run(runtime, "water.prime", {"litres": 60})
    run(runtime, "pump.prime")
    run(runtime, "pump.start")
    run(runtime, "pump.stroke", {"volume_m3": 0.32})
    run(runtime, "pump.pressure", {"reading_mpa": 5.4})
    run(runtime, "pump.finish")
    run(runtime, "sampler.draw", {"litres": 12})
    run(runtime, "sampler.release")
    run(runtime, "sampler.file", {"litres": 12})
    run(runtime, "mix.stop", {"residual_kg": 3.0})
    run(runtime, "audit.rollup")
