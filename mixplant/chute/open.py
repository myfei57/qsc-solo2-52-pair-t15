"""Opening the door is gated on the finished mixing window."""

from __future__ import annotations

from typing import Any

from ..errors import OrderViolationError


def require_window_finished(*, finished: bool, remaining: int, batch_id: str) -> None:
    """Refuse to open the door while the mix is still turning."""

    if not finished:
        raise OrderViolationError(
            "the discharge door may not open before the mixing window finishes",
            batch_id=batch_id,
            remaining_ticks=remaining,
        )


def open_payload(*, batch_id: str, window_ticks: int) -> dict[str, Any]:
    """Build the record body for one door opening."""

    return {"active": True, "batch_id": batch_id, "window_ticks": window_ticks}
