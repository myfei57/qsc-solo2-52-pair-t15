"""The pump may not start before the line is primed."""

from __future__ import annotations

import pytest

from mixplant.errors import InterlockBlockedError, OrderViolationError
from mixplant.pump.pressure import pressure_reading
from mixplant.pump.runloop import RunLoop
from mixplant.pump.start import require_primed, start_payload
from mixplant.runtime import PlantRuntime
from tests.support import run


def test_prime_requirement() -> None:
    require_primed(primed_l=60.0, minimum_l=40.0)
    with pytest.raises(OrderViolationError):
        require_primed(primed_l=10.0, minimum_l=40.0)
    assert start_payload(primed_l=60.0, stroke_l=320.0)["stroke_l"] == 320.0


def test_runloop_accumulates_strokes() -> None:
    run_loop = RunLoop()
    run_loop.start()
    run_loop.add(0.3)
    run_loop.add(0.3)
    assert run_loop.volume_m3 == pytest.approx(0.6)
    run_loop.stop()
    assert run_loop.describe()["strokes"] == 2


def test_pressure_reading_uses_the_configured_ceiling(runtime: PlantRuntime) -> None:
    reading = pressure_reading(thresholds=runtime.thresholds, reading_mpa=9.5)
    assert reading.ok is False
    assert reading.code == "over_limit"


def test_pump_start_is_refused_without_a_prime(runtime: PlantRuntime) -> None:
    with pytest.raises(InterlockBlockedError):
        run(runtime, "pump.start")


def test_pump_starts_once_the_prime_is_confirmed(runtime: PlantRuntime) -> None:
    run(runtime, "water.prime", {"litres": 60})
    run(runtime, "pump.prime")
    result = run(runtime, "pump.start")
    assert result["start"]["primed_l"] == 60.0
    assert runtime.pump.status()["running"] is True
