"""Subscribers that give the bus its two jobs."""

from __future__ import annotations

from typing import Any, Iterable

from ..store.records import Record
from ..store.repository import RecordRepository
from .bus import Event
from .topics import ALARM

AUDIT_KIND = "audit.event"


class AuditSubscriber:
    """Copies every topic event into the record stream.

    The copy is a durable side effect, so the handler is idempotent: an
    event whose sequence is already in the stream is skipped, which keeps a
    repeated replay from writing the same copy twice.
    """

    __slots__ = ("_repository", "_seen", "_copied")

    def __init__(self, repository: RecordRepository) -> None:
        self._repository = repository
        self._seen = 0
        self._copied: set[int] = set()

    def __call__(self, event: Event) -> None:
        self.handle(event)

    def hydrate(self, records: Iterable[Record]) -> None:
        """Adopt the sequences a previous process already copied."""

        for record in records:
            seq = record.payload.get("event_seq")
            if seq:
                self._copied.add(int(seq))

    def handle(self, event: Event) -> None:
        if event.seq and event.seq in self._copied:
            return
        self._repository.publish(
            AUDIT_KIND,
            event.origin,
            int(event.payload.get("generation", 0) or 0),
            {
                "topic": event.topic,
                "name": event.name,
                "origin": event.origin,
                "tick": event.tick,
                "event_seq": event.seq,
            },
        )
        if event.seq:
            self._copied.add(event.seq)
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
