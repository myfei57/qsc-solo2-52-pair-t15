"""Discharge service: the door, the queue, the loads and the confirmations."""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ..recipe.service import RecipeService
from ..service_base import PlantService
from ..statemachine.phases import MixPhase
from .chute import DOOR_KIND, LOAD_KIND, MANIFEST_KIND, OPEN_KIND, QUEUE_KIND
from .door import door_state
from .load import load_record
from .manifest import LoadManifest
from .open import open_payload, require_window_finished
from .queue import TruckQueue


class ChuteService(PlantService):
    """Opens the discharge door only after the mixing window has finished."""

    origin = "chute"
    line = "mix"
    subject = "chute"

    def __init__(self, context, recipes: RecipeService, machine=None) -> None:
        super().__init__(context, machine)
        self.recipes = recipes
        self.queue = TruckQueue()
        self.manifest = LoadManifest()
        self._open_batch: str | None = None

    def arrive(self, truck_id: str) -> dict[str, Any]:
        """Queue a truck for loading."""

        position = self.queue.arrive(truck_id)
        self.publish(QUEUE_KIND, {"active": True, **self.queue.describe()})
        self.emit("chute.truck_queued", {"truck_id": truck_id, "position": position})
        return {"queue": self.queue.describe(), "position": position}

    def open_door(self) -> dict[str, Any]:
        """Open the door; the mixing window has to be finished first."""

        self.require("chute.open", required_phase=MixPhase.MIXED.value)
        timer = self.payload_entry("mix", "timer")
        batch = self.context.batches.latest()
        batch_id = "" if batch is None else batch.batch_id
        require_window_finished(
            finished=bool(timer.get("finished", False)) if timer else False,
            remaining=int(timer.get("remaining", 0)) if timer else 0,
            batch_id=batch_id,
        )
        length = int(timer.get("length", 0)) if timer else 0
        self._open_batch = batch_id
        self.publish(DOOR_KIND, door_state(open=True, batch_id=batch_id).describe())
        self.publish(OPEN_KIND, open_payload(batch_id=batch_id, window_ticks=length))
        self.emit("chute.door_opened", {"batch_id": batch_id})
        return {"door": door_state(open=True, batch_id=batch_id).describe(), "queue": self.queue.describe()}

    def load(self, *, truck_id: str, volume_m3: float) -> dict[str, Any]:
        """Hand one truck its load, in queue order."""

        self.require("chute.load")
        if self._open_batch is None:
            raise NotFoundError("the discharge door is not open")
        served = self.queue.serve(truck_id)
        record = load_record(
            truck_id=served,
            batch_id=self._open_batch,
            volume_m3=volume_m3,
            tick=self.context.clock.now(),
        )
        self.manifest.record(record)
        self.publish(LOAD_KIND, record.describe())
        self.publish(MANIFEST_KIND, {"active": True, **self.manifest.describe()})
        if self.machine.is_at(MixPhase.MIXED.value):
            self.advance(MixPhase.DISCHARGED.value, "truck loaded from the discharge door")
        self.emit("chute.loaded", record.describe())
        return {"load": record.describe(), "manifest": self.manifest.describe()}

    def confirm(self, *, truck_id: str, volume_m3: float) -> dict[str, Any]:
        """Confirm a truck load; confirmations are served in arrival order."""

        self.require("chute.confirm")
        record = self.manifest.require(truck_id)
        if abs(record.volume_m3 - volume_m3) > 0.5:
            self.raise_alarm(
                "chute.volume_mismatch",
                {"truck_id": truck_id, "recorded": record.volume_m3, "confirmed": volume_m3},
            )
        self.publish(LOAD_KIND, {**record.describe(), "confirmed": True, "confirmed_m3": round(volume_m3, 4)})
        self.emit("chute.confirmed", {"truck_id": truck_id})
        return {"confirmed": record.describe(), "manifest": self.manifest.describe()}

    def close_door(self) -> dict[str, Any]:
        """Close the door and end the loading window."""

        self.require("chute.close")
        batch_id = self._open_batch or ""
        self._open_batch = None
        self.publish(DOOR_KIND, door_state(open=False, batch_id=batch_id).describe())
        self.emit("chute.door_closed", {"batch_id": batch_id})
        return {"door": door_state(open=False, batch_id=batch_id).describe(), "manifest": self.manifest.describe()}

    def status(self) -> dict[str, Any]:
        door = self.payload_entry("chute", "door")
        load = self.payload_entry("chute", "load")
        manifest = self.manifest.describe()
        if self._open_batch:
            manifest["batch_loads"] = [
                item.describe() for item in self.manifest.for_batch(self._open_batch)
            ]
        return {
            "door_open": bool(door.get("active", False)) if door else False,
            "open_batch": None if door is None else door.get("batch_id"),
            "queue": self.queue.describe(),
            "manifest": manifest,
            "last_load": None if load is None else dict(load),
        }
