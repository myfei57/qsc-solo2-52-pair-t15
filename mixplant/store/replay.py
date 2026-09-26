"""Rebuild state by replaying the surviving records."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .records import Record
from .tombstone import effective_records


def reduce_state(records: Iterable[Record]) -> dict[str, Any]:
    """Fold records into a nested ``{group: {leaf: payload}}`` mapping."""

    state: dict[str, Any] = {}
    for rec in records:
        if rec.is_tombstone:
            continue
        bucket = state.setdefault(rec.group, {})
        entry: dict[str, Any] = dict(rec.payload)
        entry.setdefault("tick", rec.tick)
        entry.setdefault("generation", rec.generation)
        entry.setdefault("seq", rec.seq)
        entry.setdefault("origin", rec.origin)
        bucket[rec.leaf] = entry
    return state


def merge_state(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Merge ``overlay`` on top of ``base``, one leaf at a time."""

    merged: dict[str, Any] = {
        key: dict(value) if isinstance(value, Mapping) else value for key, value in base.items()
    }
    for group, leaves in overlay.items():
        if not isinstance(leaves, Mapping):
            merged[group] = leaves
            continue
        bucket = merged.setdefault(group, {})
        if not isinstance(bucket, dict):
            bucket = {}
            merged[group] = bucket
        for leaf, payload in leaves.items():
            existing = bucket.get(leaf)
            if isinstance(existing, Mapping) and isinstance(payload, Mapping):
                combined = dict(existing)
                combined.update(payload)
                bucket[leaf] = combined
            else:
                bucket[leaf] = payload
    return merged


def state_at_tick(records: Iterable[Record], tick: int) -> dict[str, Any]:
    """Return the state as it stood at ``tick``.

    Tombstones are applied only when the tick being asked about already
    contains them, so a rollback never retroactively rewrites history.
    """

    if tick < 0:
        raise ValueError("tick must not be negative")
    within = [rec for rec in records if rec.tick <= tick]
    return reduce_state(effective_records(within))
