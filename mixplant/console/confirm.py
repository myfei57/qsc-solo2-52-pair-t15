"""Truck load confirmations arrive through the console."""

from __future__ import annotations

from typing import Any, Mapping

from ..errors import ValidationError
from ..plant.tools import number, text


def confirm_payload(request_body: Mapping[str, Any]) -> dict[str, Any]:
    """Read the truck identity and the confirmed volume from a request body."""

    return {
        "truck_id": text(request_body, "truck_id"),
        "volume_m3": number(request_body, "volume_m3"),
    }


def require_volume(volume_m3: float) -> float:
    """Refuse a confirmation that cannot be a truck load."""

    if volume_m3 <= 0:
        raise ValidationError("a confirmed load must be positive", volume_m3=volume_m3)
    return volume_m3
