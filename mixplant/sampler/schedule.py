"""Deciding whether the next batch still needs a sample."""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError


def require_next_batch(batch_id: str | None, drawn: tuple[str, ...]) -> str:
    """Return the batch that still needs a sample."""

    if not batch_id:
        raise NotFoundError("no batch is available to sample")
    if batch_id in drawn:
        raise NotFoundError("this batch already produced a sample", batch_id=batch_id)
    return batch_id


def describe_schedule(*, batch_id: str | None, drawn: tuple[str, ...]) -> dict[str, Any]:
    """Describe the sampler schedule for the console."""

    return {
        "next_batch": batch_id,
        "drawn": list(drawn),
        "pending": batch_id is not None and batch_id not in drawn,
    }
