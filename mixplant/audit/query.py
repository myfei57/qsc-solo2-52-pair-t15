"""Read helpers over the audit ledger."""

from __future__ import annotations

from typing import Any

from .log import AuditLedger


def recent(log: AuditLedger, limit: int = 20) -> list[dict[str, Any]]:
    """Return the newest audited events."""

    entries = log.entries()
    return [entry.describe() for entry in entries[-limit:]]


def by_name(log: AuditLedger) -> dict[str, int]:
    """Return how often each audited event happened."""

    counts: dict[str, int] = {}
    for entry in log.entries():
        counts[entry.name] = counts.get(entry.name, 0) + 1
    return dict(sorted(counts.items()))
