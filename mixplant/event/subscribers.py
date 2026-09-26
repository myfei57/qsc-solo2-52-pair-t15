"""Subscribers that give the bus its two jobs."""

from __future__ import annotations

from typing import Any

from ..store.repository import RecordRepository
from .bus import Event
from .topics import ALARM

AUDIT_KIND = "audit.event"


class AuditSubscriber:
    """Copies every topic event into the record stream."""

    __slots__ = ("_repository", "_seen")

    def __init__(self, repository: RecordRepository) -> None:
        self._repository = repository
        self._seen = 0

    def __call__(self, event: Event) -> None:
        self.handle(event)

    def handle(self, event: Event) -> None:
        self._repository.publish(
            AUDIT_KIND,
            event.origin,
            int(event.payload.get("generation", 0) or 0),
            {"topic": event.topic, "name": event.name, "origin": event.origin, "tick": event.tick},
        )
        self._seen += 1

    def seen(self) -> int:
        """Return how many events were copied into the stream."""

        return self._seen


class AlarmCollector:
    """Keeps the newest alarms so the overview page can list them."""

    __slots__ = ("_capacity", "_alarms")

    def __init__(self, capacity: int = 32) -> None:
        if capacity < 1:
            raise ValueError("alarm capacity must be positive")
        self._capacity = capacity
        self._alarms: list[dict[str, Any]] = []

    def __call__(self, event: Event) -> None:
        self.handle(event)

    def handle(self, event: Event) -> None:
        if event.topic != ALARM:
            return
        self._alarms.append(event.describe())
        if len(self._alarms) > self._capacity:
            self._alarms = self._alarms[-self._capacity :]

    def recent(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._alarms]

    def count(self) -> int:
        return len(self._alarms)

    def clear(self) -> None:
        """Drop every collected alarm."""

        self._alarms.clear()
