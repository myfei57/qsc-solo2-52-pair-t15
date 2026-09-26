"""The batching water valve."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValveState:
    """Whether the water valve is open."""

    open: bool
    target_l: float

    def describe(self) -> dict[str, Any]:
        return {"active": self.open, "target_l": self.target_l}


def valve_state(*, open: bool, target_l: float) -> ValveState:
    """Build a valve state for a metering target."""

    return ValveState(open=open, target_l=round(target_l, 4))
