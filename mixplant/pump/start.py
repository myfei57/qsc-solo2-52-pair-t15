"""Starting the pump requires a confirmed prime."""

from __future__ import annotations

from typing import Any

from ..errors import OrderViolationError


def require_primed(*, primed_l: float, minimum_l: float) -> None:
    """Refuse a pump start when the line was never primed."""

    if primed_l < minimum_l:
        raise OrderViolationError(
            "the pump may not start before the line is primed",
            primed_l=primed_l,
            required_l=minimum_l,
        )


def start_payload(*, primed_l: float, stroke_l: float) -> dict[str, Any]:
    """Build the record body for one pump start."""

    return {"active": True, "primed_l": round(primed_l, 4), "stroke_l": round(stroke_l, 4)}
