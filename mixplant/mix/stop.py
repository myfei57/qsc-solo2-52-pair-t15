"""Stopping the mixer is only allowed once the scale hopper is clear."""

from __future__ import annotations

from typing import Any

from ..errors import ValidationError


def stop_payload(*, residual_kg: float, released: bool, reason: str) -> dict[str, Any]:
    """Build the record body for one mixer stop."""

    if residual_kg < 0:
        raise ValidationError("residual mass must not be negative", residual=residual_kg)
    if not reason:
        raise ValidationError("a mixer stop needs a reason")
    return {
        "active": True,
        "released": released,
        "residual_kg": round(residual_kg, 4),
        "reason": reason,
    }
