"""The durable outbox behind every subscription.

An event is first written to the business journal as an ``event.notify``
record and committed together with the rest of the command.  The outcome of
every delivery attempt (live or replayed) is an ``event.deliver`` record and
every replay run ends with an ``event.replay`` summary.  Keeping all three in
the same append only stream as the domain records is what makes publication,
delivery, replay and audit consistent without a second transactional system.

Records surviving tombstones define the truth a restart rebuilds from:

* ``event.notify``  - every event in global (journal) sequence order;
* ``event.deliver`` - one row per *terminal* delivery attempt, carrying the
  subscriber name, the event sequence it handled and ``replayed``;
* ``event.replay``  - one row per explicit replay run with its progress.

A subscriber's checkpoint is therefore simply the highest ``event_seq`` it
handled successfully, and its backlog is every surviving notification above
it that matches its topic filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..clock import Clock
from ..store.records import Record
from ..store.repository import RecordRepository

NOTIFY_KIND = "event.notify"
DELIVER_KIND = "event.deliver"
REPLAY_KIND = "event.replay"

# Terminal attempt outcomes written on ``event.deliver`` rows.
DELIVERED = "delivered"
FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Delivery:
    """One terminal delivery attempt, as reconstructed from the stream."""

    seq: int
    subscriber: str
    event_seq: int
    status: str
    replayed: bool
    error: str
    tick: int

    @classmethod
    def from_record(cls, record: Record) -> "Delivery":
        return cls(
            seq=record.seq,
            subscriber=str(record.payload["subscriber"]),
            event_seq=int(record.payload["event_seq"]),
            status=str(record.payload["status"]),
            replayed=bool(record.payload.get("replayed", False)),
            error=str(record.payload.get("error", "")),
            tick=record.tick,
        )


class EventOutbox:
    """Reads and writes the notification and delivery records."""

    __slots__ = ("_store", "_clock")

    def __init__(self, store: RecordRepository, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def publish_notification(self, event: Any) -> Record:
        """Stage, flush and commit one event notification.

        The event's journal sequence becomes its global order: it is monotone,
        gapless and unique.  Committing through the same repository the
        command used keeps publication and delivery auditable in one stream.
        """

        return self._store.publish(
            NOTIFY_KIND,
            event.origin,
            int(event.payload.get("generation", 0) or 0),
            {
                "topic": event.topic,
                "name": event.name,
                "origin": event.origin,
                "tick": event.tick,
                "payload": dict(event.payload),
            },
        )

    @staticmethod
    def event_from_record(record: Record) -> Any:
        """Rebuild the bus event a notification record captured."""

        from .bus import Event

        payload = record.payload
        body = payload.get("payload")
        return Event(
            topic=str(payload["topic"]),
            name=str(payload["name"]),
            origin=str(payload["origin"]),
            tick=int(payload.get("tick", record.tick)),
            payload=dict(body) if isinstance(body, Mapping) else {},
            seq=record.seq,
        )

    def notifications(self) -> tuple[Record, ...]:
        """Return every surviving notification in global sequence order."""

        return tuple(rec for rec in self._store.visible() if rec.kind == NOTIFY_KIND)

    def deliveries(self) -> tuple[Delivery, ...]:
        """Return every surviving delivery attempt in write order."""

        return tuple(
            Delivery.from_record(rec)
            for rec in self._store.visible()
            if rec.kind == DELIVER_KIND
        )

    def delivered_sequences(self, subscriber: str) -> frozenset[int]:
        """Return the event sequences ``subscriber`` already handled once."""

        return frozenset(
            attempt.event_seq
            for attempt in self.deliveries()
            if attempt.subscriber == subscriber and attempt.status == DELIVERED
        )

    def delivered_sequences_set(self) -> frozenset[int]:
        """Return every event sequence that any subscriber handled once."""

        return frozenset(
            attempt.event_seq for attempt in self.deliveries() if attempt.status == DELIVERED
        )

    def record_delivery(
        self,
        *,
        subscriber: str,
        event_seq: int,
        status: str,
        replayed: bool,
        error: str = "",
    ) -> Record:
        """Commit one terminal delivery attempt."""

        return self._store.publish(
            DELIVER_KIND,
            "console",
            0,
            {
                "active": True,
                "subscriber": subscriber,
                "event_seq": event_seq,
                "status": status,
                "replayed": bool(replayed),
                "error": error,
            },
        )

    def record_replay(self, run_id: str, report: Mapping[str, Any]) -> Record:
        """Commit one replay run summary so the run stays auditable."""

        return self._store.publish(
            REPLAY_KIND,
            "console",
            0,
            {"active": True, "run_id": run_id, **dict(report)},
        )

    def replays(self) -> tuple[Record, ...]:
        """Return every surviving replay summary in run order."""

        return tuple(rec for rec in self._store.visible() if rec.kind == REPLAY_KIND)
