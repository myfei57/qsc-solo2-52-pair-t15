"""Durable delivery bookkeeping for the event bus.

The bus journals every event *before* it delivers (write ahead), then journals
one outcome per subscriber and attempt.  Both live in the same record stream
as everything else, so delivery, replay and audit share one watermark, one
snapshot and one query surface.

Replay is a foreground, visible action by decision: it runs inside bootstrap
and inside the explicit ``bus.replay`` command, never on a hidden background
thread, and every recovered event leaves a ``bus.delivery`` record with the
status ``replayed`` so an operator can see exactly what was caught up.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Mapping, Protocol

from ..store.repository import RecordRepository

if TYPE_CHECKING:
    from .bus import Event

BUS_EVENT_KIND = "bus.event"
BUS_DELIVERY_KIND = "bus.delivery"
BUS_REPLAY_KIND = "bus.replay"

STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_REPLAYED = "replayed"
SETTLED = (STATUS_OK, STATUS_REPLAYED)


class ReplayMode:
    """How a subscriber catches up on missed events."""

    SEQUENTIAL = "sequential"
    SHARDED = "sharded"

    ALL = (SEQUENTIAL, SHARDED)


@dataclass(frozen=True, slots=True)
class Outcome:
    """One journaled delivery attempt."""

    event_seq: int
    subscriber: str
    status: str
    attempt: int
    error: str | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "event_seq": self.event_seq,
            "subscriber": self.subscriber,
            "status": self.status,
            "attempt": self.attempt,
            "error": self.error,
        }


class DeliveryLog(Protocol):
    """Where the bus writes events and outcomes down."""

    def append_event(self, event: "Event") -> int:
        """Journal ``event`` before any delivery and return its sequence."""

    def append_outcome(self, outcome: Outcome) -> None:
        """Journal how one delivery attempt ended."""

    def append_replay(self, summary: Mapping[str, Any]) -> None:
        """Journal the result of one subscriber's replay run."""

    def flush(self) -> None:
        """Make everything staged so far durable and committed."""

    def events(self) -> tuple["Event", ...]:
        """Return every journaled event in publish order, sequences attached."""

    def outcomes(self) -> tuple[Outcome, ...]:
        """Return every journaled outcome in write order."""


class MemoryDeliveryLog:
    """A delivery log that never leaves the process."""

    __slots__ = ("_events", "_outcomes", "_replays")

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._outcomes: list[Outcome] = []
        self._replays: list[Mapping[str, Any]] = []

    def append_event(self, event: "Event") -> int:
        seq = len(self._events) + 1
        self._events.append(replace(event, seq=seq))
        return seq

    def append_outcome(self, outcome: Outcome) -> None:
        self._outcomes.append(outcome)

    def append_replay(self, summary: Mapping[str, Any]) -> None:
        self._replays.append(dict(summary))

    def flush(self) -> None:
        return None

    def events(self) -> tuple["Event", ...]:
        return tuple(self._events)

    def outcomes(self) -> tuple[Outcome, ...]:
        return tuple(self._outcomes)

    def replays(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(item) for item in self._replays)


class StoreDeliveryLog:
    """A delivery log that rides the plant wide record stream."""

    __slots__ = ("_store", "_staged")

    def __init__(self, store: RecordRepository) -> None:
        self._store = store
        self._staged = 0

    def append_event(self, event: "Event") -> int:
        record = self._store.stage(
            BUS_EVENT_KIND,
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
        self._staged += 1
        return record.seq

    def append_outcome(self, outcome: Outcome) -> None:
        self._store.stage(
            BUS_DELIVERY_KIND,
            "bus",
            0,
            {
                "event_seq": outcome.event_seq,
                "subscriber": outcome.subscriber,
                "status": outcome.status,
                "attempt": outcome.attempt,
                "error": outcome.error,
            },
        )
        self._staged += 1

    def append_replay(self, summary: Mapping[str, Any]) -> None:
        self._store.stage(BUS_REPLAY_KIND, "bus", 0, dict(summary))
        self._staged += 1

    def flush(self) -> None:
        if not self._staged:
            return  # a repeated trigger must not leave fresh journal entries
        self._store.flush()
        if self._store.last_seq() > self._store.watermark().committed_seq:
            self._store.commit_through(self._store.last_seq())
        self._staged = 0

    def events(self) -> tuple["Event", ...]:
        from .bus import Event

        return tuple(
            Event(
                topic=str(record.payload["topic"]),
                name=str(record.payload["name"]),
                origin=str(record.payload["origin"]),
                tick=int(record.payload["tick"]),
                payload=dict(record.payload.get("payload") or {}),
                seq=record.seq,
            )
            for record in self._store.visible()
            if record.kind == BUS_EVENT_KIND
        )

    def outcomes(self) -> tuple[Outcome, ...]:
        return tuple(
            Outcome(
                event_seq=int(record.payload["event_seq"]),
                subscriber=str(record.payload["subscriber"]),
                status=str(record.payload["status"]),
                attempt=int(record.payload.get("attempt", 1)),
                error=record.payload.get("error"),
            )
            for record in self._store.visible()
            if record.kind == BUS_DELIVERY_KIND
        )
