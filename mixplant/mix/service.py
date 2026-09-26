"""Mixer service: feed order, mixing window, sampling schedule and stop order."""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ..recipe.service import RecipeService
from ..service_base import PlantService
from ..statemachine.phases import MixPhase
from .cycle import CycleTracker
from .feed import feed_step
from .mix import (
    CEMENT,
    CYCLE_KIND,
    FEED_KIND,
    MIXER_KIND,
    REPORT_KIND,
    SCHEDULE_KIND,
    STOP_KIND,
    TIMER_KIND,
    WATER,
)
from .report import mix_report
from .schedule import require_batch, sample_due
from .sequence import describe_order, fed_sequence
from .stop import stop_payload
from .timer import MixTimer


class MixService(PlantService):
    """Runs one mixing cycle at a time and gates discharge on the window."""

    origin = "mix"
    line = "mix"
    subject = "mix"

    def __init__(self, context, recipes: RecipeService, machine=None) -> None:
        super().__init__(context, machine)
        self.recipes = recipes
        self.timer = MixTimer()
        self.cycles = CycleTracker()
        self._fed: tuple[str, ...] = ()

    def start(self) -> dict[str, Any]:
        """Start the mixer and open a cycle for the current batch."""

        batch = self.context.batches.latest()
        if batch is None:
            raise NotFoundError("declare a batch before starting the mixer")
        cycle = self.cycles.begin(batch.batch_id, self.recipes.current_version(), tick=self.context.clock.now())
        self._fed = ()
        self.publish(MIXER_KIND, {"active": True, "batch_id": cycle.batch_id})
        self.publish(CYCLE_KIND, cycle.describe())
        self.emit("mix.started", cycle.describe())
        return {"cycle": cycle.describe(), "order": describe_order()}

    def feed(self, *, component: str) -> dict[str, Any]:
        """Take one input in the declared order: water before cement."""

        action = "mix.water_in" if component == WATER else "mix.cement_in"
        self.require(action)
        step = feed_step(component, self._fed, tick=self.context.clock.now())
        self._fed = step.order
        self.publish(
            FEED_KIND,
            {
                "active": True,
                "component": step.component,
                "order": list(step.order),
                "version": self.recipes.current_version(),
            },
        )
        self.emit("mix.fed", step.describe())
        return {"input": step.describe(), "order": describe_order()}

    def begin_timer(self) -> dict[str, Any]:
        """Start the mixing window once every input has been fed."""

        self.require("mix.time")
        if self._fed != (WATER, CEMENT):
            raise NotFoundError("both inputs must be fed before the window starts", fed=list(self._fed))
        cycle = self.cycles.require_current()
        length = self.recipes.current().mix_time_ticks
        deadline = self.timer.start(tick=self.context.clock.now(), length=length)
        self.publish(TIMER_KIND, self.timer.payload(self.context.clock.now(), finished=False))
        if self.machine.is_at(MixPhase.CEMENT_IN.value):
            self.advance(MixPhase.MIXING.value, "mixing window started")
        self.emit("mix.window_started", {"batch_id": cycle.batch_id, "deadline": deadline})
        return {"timer": self.timer.payload(self.context.clock.now(), finished=False), "deadline": deadline}

    def finish_timer(self) -> dict[str, Any]:
        """Close the mixing window once its ticks have elapsed."""

        now = self.context.clock.now()
        self.timer.require_finished(now)
        self.publish(TIMER_KIND, self.timer.payload(now, finished=True))
        if self.machine.is_at(MixPhase.MIXING.value):
            self.advance(MixPhase.MIXED.value, "mixing window has finished")
        self.emit("mix.window_finished", {"batch_id": self.cycles.require_current().batch_id})
        return {"timer": self.timer.payload(now, finished=True)}

    def schedule_sample(self) -> dict[str, Any]:
        """Mark the finished mix as due for a laboratory sample."""

        batch = self.context.batches.latest()
        batch_id = require_batch(batch.batch_id if batch else None)
        due = sample_due(
            state=self.state(),
            limits=self.context.config.limits,
            batch_id=batch_id,
            now=self.context.clock.now(),
        )
        self.publish(SCHEDULE_KIND, {"active": True, **due.describe()})
        self.emit("mix.sample_scheduled", due.describe())
        return {"schedule": due.describe()}

    def stop(self, *, residual_kg: float, reason: str = "batch complete") -> dict[str, Any]:
        """Stop the mixer; the scale hopper must already be clear."""

        self.require("mix.stop")
        hopper = self.payload_entry("agg", "hopper")
        payload = stop_payload(residual_kg=residual_kg, released=hopper is not None, reason=reason)
        cycle = self.cycles.require_current()
        report = mix_report(
            cycle=cycle,
            timer=self.timer,
            now=self.context.clock.now(),
            inputs={"order": list(self._fed)},
        )
        self.publish(REPORT_KIND, {"active": True, **report})
        self.publish(STOP_KIND, payload)
        self.publish(MIXER_KIND, {"active": False, "batch_id": cycle.batch_id})
        self.cycles.complete(tick=self.context.clock.now())
        self.timer.cancel()
        self.rewind(MixPhase.IDLE.value, "batch complete, mixer ready for the next recipe")
        self.emit("mix.stopped", payload)
        return {"stop": payload, "report": report}

    def inputs(self) -> tuple[str, ...]:
        return self._fed

    def status(self) -> dict[str, Any]:
        mixer = self.payload_entry("mix", "mixer")
        timer = self.payload_entry("mix", "timer")
        schedule = self.payload_entry("mix", "schedule")
        cycle = self.cycles.current()
        return {
            "phase": self.machine.phase,
            "sequence": self.machine.order(),
            "next_phase": self.machine.next_phase(),
            "running": bool(mixer.get("active", False)) if mixer else False,
            "inputs": fed_sequence(self._fed),
            "order": list(self._fed),
            "window": None if timer is None else dict(timer),
            "sample_due": bool(schedule.get("due", False)) if schedule else False,
            "batch_id": None if cycle is None else cycle.batch_id,
            "completed": list(self.cycles.completed()),
            "feed_order": describe_order(),
            "cement_fed": CEMENT in self._fed,
        }
