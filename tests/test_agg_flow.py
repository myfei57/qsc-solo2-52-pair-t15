"""Aggregate weighing, calibration and the durable-before-drop rule."""

from __future__ import annotations

import pytest

from mixplant.agg.calibrate import calibrate
from mixplant.agg.check import check_dry_weight, planned_total
from mixplant.agg.scale import deviation_percent, within_tolerance
from mixplant.agg.weigh import reading_from_payload, weigh
from mixplant.errors import InterlockBlockedError, NotDurableError
from mixplant.runtime import PlantRuntime
from tests.support import publish_and_select, run


def test_deviation_and_tolerance() -> None:
    assert deviation_percent(102.0, 100.0) == pytest.approx(2.0)
    assert within_tolerance(2.0, 2.0) is True
    assert within_tolerance(2.1, 2.0) is False


def test_weigh_marks_a_reading_out_of_tolerance_as_not_ok() -> None:
    reading = weigh(bin_name="bin-1", material="sand", target_kg=1000, actual_kg=1100, tolerance_percent=2.0)
    assert reading.ok is False
    assert reading_from_payload(reading.describe()).actual_kg == 1100


def test_calibration_is_applied() -> None:
    calibration = calibrate(slope=1.02, offset=-3.0)
    assert calibration.apply(1000.0) == pytest.approx(1017.0)


def test_dry_check_excludes_water() -> None:
    materials = {"sand": 800.0, "cement": 330.0, "water": 175.0}
    assert planned_total(materials, exclude=("water",)) == pytest.approx(1130.0)
    check = check_dry_weight(materials=materials, actual_kg=1130.0, tolerance_percent=2.0, exclude=("water",))
    assert check.ok is True


def test_drop_is_refused_before_the_weight_is_durable(runtime: PlantRuntime) -> None:
    publish_and_select(runtime)
    run(runtime, "batch.declare", {"batch_id": "B-001", "quantity": 6})
    run(runtime, "agg.map_bin", {"bin": "bin-1", "material": "sand"})
    run(runtime, "agg.weigh", {"bin": "bin-1", "actual_kg": 4800})
    with pytest.raises(NotDurableError):
        run(runtime, "agg.drop")


def test_drop_succeeds_after_the_weight_is_durable(runtime: PlantRuntime) -> None:
    publish_and_select(runtime)
    run(runtime, "batch.declare", {"batch_id": "B-001", "quantity": 6})
    run(runtime, "agg.map_bin", {"bin": "bin-1", "material": "sand"})
    run(runtime, "agg.weigh", {"bin": "bin-1", "actual_kg": 4800})
    run(runtime, "agg.persist")
    assert run(runtime, "agg.drop")["dropped"] >= 1


def test_weighing_needs_a_refreshed_bin_mapping(runtime: PlantRuntime) -> None:
    publish_and_select(runtime)
    run(runtime, "batch.declare", {"batch_id": "B-001", "quantity": 6})
    with pytest.raises(InterlockBlockedError):
        run(runtime, "agg.weigh", {"bin": "bin-1", "actual_kg": 4800})
