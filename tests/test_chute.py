"""The discharge door and the truck queue."""

from __future__ import annotations

import pytest

from mixplant.chute.manifest import LoadManifest
from mixplant.chute.load import load_record
from mixplant.chute.queue import TruckQueue
from mixplant.errors import DuplicateError, NotFoundError, ValidationError
from mixplant.runtime import PlantRuntime
from tests.support import run, run_full_cycle


def test_queue_is_first_in_first_out() -> None:
    queue = TruckQueue()
    queue.arrive("T-01")
    queue.arrive("T-02")
    assert queue.head() == "T-01"
    with pytest.raises(ValidationError):
        queue.serve("T-02")
    assert queue.serve("T-01") == "T-01"
    assert queue.order() == ["T-02"]


def test_queue_refuses_a_duplicate_truck() -> None:
    queue = TruckQueue()
    queue.arrive("T-01")
    with pytest.raises(DuplicateError):
        queue.arrive("T-01")


def test_empty_queue_refuses_a_head() -> None:
    with pytest.raises(NotFoundError):
        TruckQueue().head()


def test_manifest_refuses_a_second_load_for_one_truck() -> None:
    manifest = LoadManifest()
    manifest.record(load_record(truck_id="T-01", batch_id="B-1", volume_m3=6.0, tick=1))
    with pytest.raises(DuplicateError):
        manifest.record(load_record(truck_id="T-01", batch_id="B-1", volume_m3=6.0, tick=2))


def test_loads_follow_the_queue(runtime: PlantRuntime) -> None:
    run_full_cycle(runtime)
    assert runtime.chute.status()["door_open"] is False
    assert runtime.chute.manifest.describe()["trucks"] == ["T-01"]


def test_queue_reports_waiting_trucks(runtime: PlantRuntime) -> None:
    run(runtime, "chute.arrive", {"truck_id": "T-09"})
    run(runtime, "chute.arrive", {"truck_id": "T-10"})
    assert runtime.chute.status()["queue"]["order"] == ["T-09", "T-10"]
