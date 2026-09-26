"""The mixer takes its inputs in order and gates discharge on the window."""

from __future__ import annotations

import pytest

from mixplant.errors import InterlockBlockedError, OrderViolationError
from mixplant.mix.sequence import describe_order, fed_sequence, order_index, require_turn
from mixplant.mix.timer import MixTimer
from mixplant.runtime import PlantRuntime
from tests.support import advance_to_mixing, run, start_mixer


def test_declared_input_order() -> None:
    assert describe_order()["order"] == ["water", "cement"]
    assert order_index("cement") == 1
    require_turn("water", ())
    with pytest.raises(OrderViolationError):
        require_turn("cement", ())
    assert fed_sequence(("cement", "water")) == ["water", "cement"]


def test_timer_needs_to_finish() -> None:
    timer = MixTimer()
    deadline = timer.start(tick=10, length=6)
    assert deadline == 16
    with pytest.raises(OrderViolationError):
        timer.require_finished(15)
    timer.require_finished(16)
    assert timer.payload(16, finished=True)["finished"] is True


def test_cement_may_only_be_fed_after_the_water(runtime: PlantRuntime) -> None:
    start_mixer(runtime)
    with pytest.raises(InterlockBlockedError):
        run(runtime, "mix.feed", {"component": "cement"})


def test_discharge_is_refused_before_the_window_finishes(runtime: PlantRuntime) -> None:
    advance_to_mixing(runtime)
    with pytest.raises(InterlockBlockedError):
        run(runtime, "chute.open")


def test_mixer_stop_needs_a_released_hopper(runtime: PlantRuntime) -> None:
    start_mixer(runtime)
    with pytest.raises(InterlockBlockedError):
        run(runtime, "mix.stop", {"residual_kg": 4.0})
