"""The discharge door state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DoorState:
    """Whether the discharge door is open for a batch."""

    open: bool
    batch_id: str

    def describe(self) -> dict[str, Any]:
        return {"active": self.open, "batch_id": self.batch_id}


def door_state(*, open: bool, batch_id: str) -> DoorState:
    """Build a door state for one batch."""

    return DoorState(open=open, batch_id=batch_id)
