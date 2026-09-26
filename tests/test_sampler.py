"""The sampler latch must be released before the next draw."""

from __future__ import annotations

import pytest

from mixplant.errors import InterlockBlockedError, OrderViolationError
from mixplant.sampler.batchset import BatchSet
from mixplant.sampler.record import sample_record
from mixplant.sampler.schedule import describe_schedule, require_next_batch
from mixplant.runtime import PlantRuntime
from tests.support import advance_to_mixed, run


def test_latch_cannot_be_cleared_before_it_is_set() -> None:
    from mixplant.statemachine.latch import Latch

    latch = Latch("sampler.draw")
    with pytest.raises(OrderViolationError):
        latch.clear(tick=1, reason="nothing to release")


def test_batchset_refuses_a_repeat() -> None:
    batchset = BatchSet()
    batchset.add("B-1")
    with pytest.raises(Exception):
        batchset.add("B-1")
    assert batchset.contains("B-1") is True


def test_schedule_reports_a_pending_batch() -> None:
    assert require_next_batch("B-2", ("B-1",)) == "B-2"
    assert describe_schedule(batch_id="B-2", drawn=("B-1",))["pending"] is True
    with pytest.raises(Exception):
        require_next_batch(None, ())


def test_sample_needs_a_batch_and_a_volume() -> None:
    record = sample_record(sample_id="sample-000001", batch_id="B-1", grade="C30", litres=12)
    assert record.describe()["litres"] == 12.0
    with pytest.raises(Exception):
        sample_record(sample_id="", batch_id="B-1", grade="C30", litres=0)


def test_second_draw_is_blocked_until_the_latch_is_released(runtime: PlantRuntime) -> None:
    advance_to_mixed(runtime)
    run(runtime, "sampler.draw", {"litres": 12})
    assert runtime.sampler.latch.latched is True
    with pytest.raises(InterlockBlockedError):
        run(runtime, "sampler.draw", {"litres": 12})
    run(runtime, "sampler.release")
    assert runtime.sampler.latch.latched is False
