"""Sampler service: the draw latch must be released before the next draw."""

from __future__ import annotations

from typing import Any, Mapping

from ..errors import NotFoundError
from ..recipe.service import RecipeService
from ..service_base import PlantService
from ..statemachine.latch import Latch
from .batchset import BatchSet
from .draw import draw_record
from .record import sample_record
from .sampler import BATCHSET_KIND, DRAW_KIND, LATCH_KIND, RECORD_KIND
from .schedule import describe_schedule, require_next_batch

DRAW_LATCH = "sampler.draw"


class SamplerService(PlantService):
    """Draws one sample per batch and latches until the draw is acknowledged."""

    origin = "sampler"
    line = "delivery"
    subject = "sampler"

    def __init__(self, context, recipes: RecipeService, machine=None) -> None:
        super().__init__(context, machine)
        self.recipes = recipes
        self.latch = Latch(DRAW_LATCH)
        self.batches = BatchSet()
        self._samples: list[dict[str, Any]] = []

    def draw(self, *, litres: float) -> dict[str, Any]:
        """Draw a sample once the mixing window has finished."""

        self.require("sampler.draw")
        batch = self.context.batches.latest()
        batch_id = require_next_batch(batch.batch_id if batch else None, self.batches.drawn())
        event = self.latch.set(tick=self.context.clock.now(), reason="sample drawn")
        self.publish(LATCH_KIND, {"active": True, **event.describe()})
        record = draw_record(batch_id=batch_id, litres=litres, tick=self.context.clock.now())
        self.publish(DRAW_KIND, record.describe())
        self.emit("sampler.drawn", record.describe())
        return {"draw": record.describe(), "latch": self.latch.describe()}

    def release(self) -> dict[str, Any]:
        """Release the draw latch so the next batch can be sampled."""

        self.require("sampler.reset")
        event = self.latch.clear(tick=self.context.clock.now(), reason="draw acknowledged")
        self.publish(LATCH_KIND, {"active": False, **event.describe()})
        self.emit("sampler.released", event.describe())
        return {"latch": self.latch.describe()}

    def file(self, *, litres: float) -> dict[str, Any]:
        """File the laboratory sample that belongs to the current batch."""

        batch = self.context.batches.latest()
        if batch is None:
            raise NotFoundError("no batch is available to file a sample for")
        self.batches.add(batch.batch_id)
        record = sample_record(
            sample_id=self.context.ids.next("sample"),
            batch_id=batch.batch_id,
            grade=batch.grade,
            litres=litres,
        )
        self.publish(RECORD_KIND, record.describe())
        self.publish(BATCHSET_KIND, {"active": True, **self.batches.describe()})
        self.emit("sampler.filed", record.describe())
        self._samples.append(record.describe())
        return {"sample": record.describe(), "batchset": self.batches.describe()}

    def samples(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._samples)

    def status(self) -> dict[str, Any]:
        latch = self.payload_entry("sampler", "latch")
        draw = self.payload_entry("sampler", "draw")
        record = self.payload_entry("sampler", "record")
        batch = self.context.batches.latest()
        return {
            "latched": bool(latch.get("active", False)) if latch else self.latch.latched,
            "step": self.latch.step,
            "drawn": list(self.batches.drawn()),
            "last_draw": None if draw is None else dict(draw),
            "last_sample": None if record is None else dict(record),
            "samples": len(self._samples),
            "phase": self.machine.phase,
            "schedule": describe_schedule(
                batch_id=None if batch is None else batch.batch_id,
                drawn=self.batches.drawn(),
            ),
        }
