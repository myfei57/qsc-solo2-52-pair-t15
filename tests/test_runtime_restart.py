"""A restart rebuilds the recipe, the batch and the stage machines."""

from __future__ import annotations

from mixplant.config import StationConfig
from mixplant.runtime import PlantRuntime
from tests.support import batch_and_weigh, publish_and_select, run


def test_restart_restores_the_recipe_and_batch(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    batch_and_weigh(first)
    first.close()

    second = PlantRuntime(config)
    report = second.bootstrap()
    assert report["replayed_records"] >= 1
    assert second.recipes.book.selected_name() == "mix-a"
    assert second.batches.latest() is not None
    assert second.machines["batch"].phase == "weighed"
    second.close()


def test_restart_restores_the_sampler_latch(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    publish_and_select(first)
    run(first, "batch.declare", {"batch_id": "B-001", "quantity": 6})
    run(first, "agg.map_bin", {"bin": "bin-1", "material": "sand"})
    run(first, "moist.compensate", {"material": "sand", "moisture_percent": 4.5, "quantity": 6})
    run(first, "agg.weigh", {"bin": "bin-1", "actual_kg": 4800})
    run(first, "agg.persist")
    run(first, "agg.drop")
    run(first, "mix.start")
    run(first, "water.open_valve", {"target_l": 1050})
    run(first, "water.dispense", {"litres": 1050, "rate_lps": 45})
    run(first, "mix.feed", {"component": "water"})
    run(first, "cement.open_gate", {"silo": "silo-1", "target_kg": 1980})
    run(first, "cement.close_gate", {"silo": "silo-1", "mass_kg": 1980, "rate_kgs": 30})
    run(first, "mix.feed", {"component": "cement"})
    run(first, "mix.time")
    run(first, "clock.advance", {"ticks": 8})
    run(first, "mix.finish")
    run(first, "sampler.draw", {"litres": 12})
    assert first.sampler.latch.latched is True
    first.close()

    second = PlantRuntime(config)
    second.bootstrap()
    assert second.sampler.latch.latched is True
    assert second.sampler.latch.step >= 1
    second.close()


def test_snapshot_shortens_the_replay(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    batch_and_weigh(first)
    snapshot = run(first, "snapshot.take")
    assert snapshot["snapshot"]["watermark_seq"] >= 1
    run(first, "agg.release", {"residual_kg": 2.0})
    first.close()

    second = PlantRuntime(config)
    report = second.bootstrap()
    assert report["used_snapshot_id"] is not None
    second.close()
