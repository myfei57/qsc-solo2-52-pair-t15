"""The in memory ledger of audited events."""

from __future__ import annotations

from typing import Any, Mapping

from .record import AuditEntry


class AuditLedger:
    """Keeps every audited event of the current shift."""

    __slots__ = ("_capacity", "_entries")

    def __init__(self, capacity: int = 512) -> None:
        if capacity < 1:
            raise ValueError("ledger capacity must be positive")
        self._capacity = capacity
        self._entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> AuditEntry:
        self._entries.append(entry)
        if len(self._entries) > self._capacity:
            self._entries = self._entries[-self._capacity :]
        return entry

    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def count(self) -> int:
        return len(self._entries)

    def origins(self) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for entry in self._entries:
            counts[entry.origin] = counts.get(entry.origin, 0) + 1
        return counts

    def describe(self, limit: int = 50) -> dict[str, Any]:
        return {
            "count": self.count(),
            "origins": dict(sorted(self.origins().items())),
            "entries": [entry.describe() for entry in self._entries[-limit:]],
        }
