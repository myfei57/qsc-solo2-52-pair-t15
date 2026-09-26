"""The declared stage order of each line."""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from ..errors import ValidationError


class BatchPhase(str, Enum):
    """Stages a batching line walks through."""

    IDLE = "idle"
    RECIPE_SELECTED = "recipe_selected"
    WEIGHING = "weighing"
    WEIGHED = "weighed"
    DROPPED = "dropped"


class MixPhase(str, Enum):
    """Stages a mixing line walks through."""

    IDLE = "idle"
    WATER_IN = "water_in"
    CEMENT_IN = "cement_in"
    MIXING = "mixing"
    MIXED = "mixed"
    DISCHARGED = "discharged"


class DeliveryPhase(str, Enum):
    """Stages a pumping and sampling line walks through."""

    IDLE = "idle"
    PRIMED = "primed"
    PUMPING = "pumping"
    DELIVERED = "delivered"


LINE_SEQUENCES: Mapping[str, tuple[Enum, ...]] = {
    "batch": tuple(BatchPhase),
    "mix": tuple(MixPhase),
    "delivery": tuple(DeliveryPhase),
}


def sequence_for(line: str) -> tuple[Enum, ...]:
    """Return the declared stage order of ``line``."""

    order = LINE_SEQUENCES.get(line)
    if order is None:
        raise ValidationError("unknown line", line=line)
    return order


def phase_names(line: str) -> list[str]:
    """Return the stage names of ``line`` in order."""

    return [str(phase.value) for phase in sequence_for(line)]
