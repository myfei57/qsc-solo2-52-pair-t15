"""The cement gate and the order it may be opened in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GateState:
    """Whether the cement gate is feeding the mixer."""

    open: bool
    silo: str
    target_kg: float

    def describe(self) -> dict[str, Any]:
        return {"active": self.open, "silo": self.silo, "target_kg": self.target_kg}


def gate_state(*, open: bool, silo: str, target_kg: float) -> GateState:
    """Build a gate state for a silo and a target mass."""

    return GateState(open=open, silo=silo, target_kg=round(target_kg, 4))
