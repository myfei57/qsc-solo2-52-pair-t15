"""Releasing the scale hopper once a batch has been dropped."""

from __future__ import annotations

from typing import Any

from ..errors import ValidationError


def release_payload(*, residual_kg: float, threshold_kg: float) -> dict[str, Any]:
    """Build the payload that closes out one batch on the scale."""

    if residual_kg < 0:
        raise ValidationError("residual mass must not be negative", residual=residual_kg)
    if threshold_kg < 0:
        raise ValidationError("residual threshold must not be negative", threshold=threshold_kg)
    return {
        "active": True,
        "residual_kg": round(residual_kg, 4),
        "threshold_kg": round(threshold_kg, 4),
        "clear": residual_kg <= threshold_kg,
    }


def describe_release(payload: Any) -> dict[str, Any]:
    """Summarise the release recorded for the current batch."""

    if not isinstance(payload, dict):
        return {"released": False, "residual_kg": None, "clear": None}
    return {
        "released": bool(payload.get("active", False)),
        "residual_kg": payload.get("residual_kg"),
        "clear": payload.get("clear"),
    }
