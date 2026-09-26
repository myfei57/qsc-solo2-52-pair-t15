"""The moisture bands a reading falls into."""

from __future__ import annotations

from enum import Enum

from ..config import Limits


class MoistureMode(str, Enum):
    """How much free water the aggregate currently carries."""

    DRY = "dry"
    WET = "wet"
    SATURATED = "saturated"


def mode_for(percent: float, limits: Limits) -> MoistureMode:
    """Classify ``percent`` against the configured moisture ceiling."""

    ceiling = limits.moisture_max_percent
    if percent <= 0.0:
        return MoistureMode.DRY
    if percent >= ceiling:
        return MoistureMode.SATURATED
    return MoistureMode.WET
