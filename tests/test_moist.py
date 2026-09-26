"""Moisture compensation runs before the dry weight check."""

from __future__ import annotations

import pytest

from mixplant.config import Limits
from mixplant.errors import ValidationError
from mixplant.moist.comp import compensate, compensated_mass, free_water, water_offset
from mixplant.moist.mode import MoistureMode, mode_for
from mixplant.moist.table import default_table
from mixplant.runtime import PlantRuntime
from tests.support import batch_and_weigh, publish_and_select, run


def test_free_water_and_wet_mass() -> None:
    assert free_water(1000.0, 5.0) == pytest.approx(50.0)
    assert compensated_mass(1000.0, 5.0) == pytest.approx(1050.0)


def test_percentage_is_validated() -> None:
    with pytest.raises(ValidationError):
        free_water(1000.0, 120.0)


def test_mode_classification() -> None:
    limits = Limits(moisture_max_percent=9.0)
    assert mode_for(0.0, limits) is MoistureMode.DRY
    assert mode_for(4.0, limits) is MoistureMode.WET
    assert mode_for(9.0, limits) is MoistureMode.SATURATED


def test_table_lookup() -> None:
    assert default_table().reference("sand") == 4.5


def test_water_offset_accumulates() -> None:
    corrections = (compensate("sand", 1000.0, 4.0), compensate("sand", 500.0, 4.0))
    assert water_offset(corrections) == pytest.approx(60.0)


def test_dry_check_is_blocked_before_compensation(runtime: PlantRuntime) -> None:
    publish_and_select(runtime)
    run(runtime, "batch.declare", {"batch_id": "B-001", "quantity": 6})
    run(runtime, "agg.map_bin", {"bin": "bin-1", "material": "sand"})
    with pytest.raises(Exception):
        run(runtime, "agg.check", {"actual_total_kg": 12000})


def test_compensation_is_required_for_the_check(runtime: PlantRuntime) -> None:
    batch_and_weigh(runtime)
    result = run(runtime, "agg.check", {"actual_total_kg": runtime.agg.describe_targets()["total_kg"] - 1050.0})
    assert result["check"]["ok"] is True
    assert runtime.moist.status()["compensated"] is True
