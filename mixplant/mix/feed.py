"""One input the mixer took."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError
from .sequence import fed_sequence, require_turn


@dataclass(frozen=True, slots=True)
class FeedStep:
    """A single input together with the order after it was taken."""

    component: str
    order: tuple[str, ...]
    tick: int

    def describe(self) -> dict[str, Any]:
        return {"component": self.component, "order": list(self.order), "tick": self.tick}


def feed_step(component: str, already_fed: tuple[str, ...], *, tick: int) -> FeedStep:
    """Record one input after checking the declared order."""

    if not component:
        raise ValidationError("feed component must not be empty")
    require_turn(component, already_fed)
    merged = tuple(fed_sequence((*already_fed, component)))
    return FeedStep(component=component, order=merged, tick=tick)
