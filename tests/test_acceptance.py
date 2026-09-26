"""A full production cycle has to pass end to end."""

from __future__ import annotations

from mixplant.runtime import PlantRuntime
from tests.support import RECIPE, batch_and_weigh, run, run_full_cycle


def test_full_cycle_reaches_every_line(cycled: PlantRuntime) -> None:
    state = cycled.state()
    assert state["lines"]["batch"]["phase"] == "dropped"
    assert state["lines"]["mix"]["phase"] == "idle"
    assert state["lines"]["delivery"]["phase"] == "delivered"
    assert state["facts"]["mix.timed"] is True
    assert state["facts"]["agg.weight_persisted"] is True


def test_cycle_records_a_load_and_a_sample(cycled: PlantRuntime) -> None:
    manifest = cycled.chute.manifest.describe()
    assert manifest["trucks"] == ["T-01"]
    assert manifest["total_m3"] == 6
    assert cycled.sampler.status()["drawn"] == ["B-001"]
    assert cycled.sampler.status()["samples"] == 1


def test_rollup_counts_the_shift(cycled: PlantRuntime) -> None:
    summary = run(cycled, "audit.rollup")
    assert summary["batches"] == 1
    assert summary["samples"] == 1
    assert summary["weight_persisted"] is True
    assert summary["mixed"] is True


def test_health_reports_every_line(runtime: PlantRuntime) -> None:
    health = runtime.health()
    assert health["status"] == "ok"
    assert set(health["lines"]) == {"batch", "mix", "delivery"}


def test_weight_is_persisted_before_the_drop(runtime: PlantRuntime) -> None:
    batch_and_weigh(runtime)
    run(runtime, "agg.drop")
    assert runtime.agg.status()["dropped"] is True
    assert runtime.agg.status()["persisted"] is True


def test_recipe_version_is_carried_into_the_batch(runtime: PlantRuntime) -> None:
    batch_and_weigh(runtime)
    batch = runtime.batches.latest()
    assert batch is not None
    assert batch.grade == "C30"
    assert batch.generation == runtime.recipes.current_version()


def test_second_batch_can_be_measured(runtime: PlantRuntime) -> None:
    run_full_cycle(runtime)
    run_full_cycle(runtime, batch_id="B-002", truck_id="T-02")
    state = runtime.state()
    assert state["batches"][0]["batch_id"] == "B-001"
    assert state["batches"][1]["batch_id"] == "B-002"
    assert state["versioned"]["confirmations"]["subjects"] == []
    assert RECIPE["name"] == runtime.recipes.book.selected_name()
    assert sorted(runtime.chute.manifest.describe()["trucks"]) == ["T-01", "T-02"]
    assert runtime.sampler.status()["drawn"] == ["B-001", "B-002"]
