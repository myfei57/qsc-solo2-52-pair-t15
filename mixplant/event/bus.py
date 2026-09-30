"""A synchronous publish and subscribe bus with durable, isolated delivery.

Every event is journaled before it is delivered, and every delivery attempt
is journaled afterwards, so a restart can see exactly what each subscriber
missed.  One subscriber raising is a partial failure: the others still get
the event and the publisher never sees the exception.

Replay is a foreground, visible action.  It runs inside bootstrap and inside
the explicit ``bus.replay`` command — never on a background thread — and it
is idempotent: an event that already reached a subscriber is never delivered
twice by a replay, and re-running a replay with nothing pending changes
nothing.  Replay order is temporal order.  A ``sequential`` subscriber is
caught up event by event in publish order and stops at the first failure so
nothing later overtakes it; a ``sharded`` subscriber is caught up per shard
key, in order inside each shard, and a failed shard never blocks the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..errors import NotFoundError, ValidationError
from .delivery import (
    SETTLED,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_REPLAYED,
    DeliveryLog,
    MemoryDeliveryLog,
    Outcome,
    ReplayMode,
)
from .topics import TOPICS

Handler = Callable[["Event"], None]
ShardKey = Callable[["Event"], str]

ALL = "*"


@dataclass(frozen=True, slots=True)
class Event:
    """One notification raised by a service.

    ``seq`` is the durable identity the bus assigns when it journals the
    event; handlers use it as their idempotency key.  It stays ``0`` for an
    event that was never published through a bus.
    """

    topic: str
    name: str
    origin: str
    tick: int
    payload: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    seq: int = 0

    def describe(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "name": self.name,
            "origin": self.origin,
            "tick": self.tick,
            "payload": dict(self.payload),
            "seq": self.seq,
        }


@dataclass(frozen=True, slots=True)
class Subscription:
    """One named handler together with its catch-up policy."""

    name: str
    topics: frozenset[str]
    handler: Handler
    mode: str = ReplayMode.SEQUENTIAL
    shard_of: ShardKey | None = None

    def matches(self, topic: str) -> bool:
        return ALL in self.topics or topic in self.topics


class EventBus:
    """Delivers every event to the subscribers registered for its topic."""

    __slots__ = ("_log", "_subscriptions", "_counter", "_names")

    def __init__(self, log: DeliveryLog | None = None) -> None:
        self._log: DeliveryLog = log if log is not None else MemoryDeliveryLog()
        self._subscriptions: list[Subscription] = []
        self._counter: dict[str, int] = {}
        self._names: list[str] = []

    def subscribe(
        self,
        topic: str,
        handler: Handler,
        *,
        name: str | None = None,
        mode: str = ReplayMode.SEQUENTIAL,
        shard_of: ShardKey | None = None,
    ) -> None:
        if not topic:
            raise ValidationError("subscription topic must not be empty")
        if topic != ALL and topic not in TOPICS:
            raise ValidationError("unknown topic", topic=topic)
        self._add_subscription(frozenset({topic}), handler, name=name, mode=mode, shard_of=shard_of)

    def subscribe_all(
        self,
        handler: Handler,
        *,
        name: str | None = None,
        mode: str = ReplayMode.SEQUENTIAL,
        shard_of: ShardKey | None = None,
    ) -> None:
        """Register a handler that sees every topic."""

        self._add_subscription(frozenset({ALL}), handler, name=name, mode=mode, shard_of=shard_of)

    def _add_subscription(
        self,
        topics: frozenset[str],
        handler: Handler,
        *,
        name: str | None,
        mode: str,
        shard_of: ShardKey | None,
    ) -> None:
        if mode not in ReplayMode.ALL:
            raise ValidationError("unknown replay mode", mode=mode)
        if mode == ReplayMode.SHARDED and shard_of is None:
            raise ValidationError("a sharded subscriber needs a shard key")
        if mode == ReplayMode.SEQUENTIAL and shard_of is not None:
            raise ValidationError("a sequential subscriber takes no shard key")
        base = name or getattr(handler, "__name__", None) or type(handler).__name__
        if name is not None and any(sub.name == base for sub in self._subscriptions):
            raise ValidationError("subscriber name must be unique", subscriber=base)
        subscriber = base
        suffix = 2
        while any(sub.name == subscriber for sub in self._subscriptions):
            subscriber = f"{base}#{suffix}"
            suffix += 1
        self._subscriptions.append(
            Subscription(
                name=subscriber,
                topics=topics,
                handler=handler,
                mode=mode,
                shard_of=shard_of,
            )
        )

    def subscriptions(self) -> tuple[Subscription, ...]:
        return tuple(self._subscriptions)

    def handlers_for(self, topic: str) -> tuple[Handler, ...]:
        return tuple(sub.handler for sub in self._subscriptions if sub.matches(topic))

    def publish(self, event: Event) -> int:
        """Deliver ``event`` and return how many subscribers accepted it."""

        if event.topic not in TOPICS:
            raise ValidationError("unknown topic", topic=event.topic)
        sequenced = replace(event, seq=self._log.append_event(event))
        delivered = 0
        for sub in self._subscriptions:
            if not sub.matches(event.topic):
                continue
            if self._deliver(sub, sequenced, replay=False) != STATUS_FAILED:
                delivered += 1
        self._log.flush()
        self._counter[event.topic] = self._counter.get(event.topic, 0) + 1
        self._names.append(event.name)
        return delivered

    def replay(self, subscriber: str | None = None) -> dict[str, Any]:
        """Catch one or every subscriber up on what it missed, in order."""

        report: dict[str, Any] = {}
        for sub in self._select(subscriber):
            pending = self._pending_events(sub)
            attempted = 0
            recovered = 0
            lanes: dict[str, int] = {}
            if sub.mode == ReplayMode.SEQUENTIAL:
                for event in pending:
                    attempted += 1
                    if self._deliver(sub, event, replay=True) == STATUS_FAILED:
                        break  # order is temporal: nothing later may overtake a failure
                    recovered += 1
            else:
                shards: dict[str, list[Event]] = {}
                for event in pending:
                    assert sub.shard_of is not None  # guaranteed at subscribe time
                    shards.setdefault(sub.shard_of(event), []).append(event)
                for key in sorted(shards):
                    lanes[key] = 0
                    for event in shards[key]:
                        attempted += 1
                        if self._deliver(sub, event, replay=True) == STATUS_FAILED:
                            break  # only this lane stops; the others keep catching up
                        recovered += 1
                        lanes[key] += 1
            remaining = len(self._pending_events(sub))
            if attempted:
                self._log.append_replay(
                    {
                        "subscriber": sub.name,
                        "mode": sub.mode,
                        "attempted": attempted,
                        "recovered": recovered,
                        "pending_after": remaining,
                        "lanes": dict(lanes),
                    }
                )
            report[sub.name] = {
                "mode": sub.mode,
                "attempted": attempted,
                "recovered": recovered,
                "pending_after": remaining,
                "lanes": dict(lanes),
            }
        self._log.flush()
        return report

    def pending(self, subscriber: str) -> tuple[int, ...]:
        """Return the sequences the named subscriber still has to catch up."""

        return tuple(event.seq for event in self._pending_events(self._one(subscriber)))

    def pending_count(self) -> int:
        """Return how many deliveries across all subscribers are still owed."""

        return sum(len(self._pending_events(sub)) for sub in self._subscriptions)

    def progress(self) -> list[dict[str, Any]]:
        """Describe every subscriber's delivery and replay position."""

        events = self._log.events()
        outcomes = self._log.outcomes()
        report = []
        for sub in self._subscriptions:
            matched = [event for event in events if sub.matches(event.topic)]
            latest: dict[int, Outcome] = {}
            for outcome in outcomes:
                if outcome.subscriber == sub.name:
                    latest[outcome.event_seq] = outcome
            pending = [
                event.seq
                for event in matched
                if latest.get(event.seq) is None or latest[event.seq].status not in SETTLED
            ]
            failures = [outcome for outcome in latest.values() if outcome.status == STATUS_FAILED]
            report.append(
                {
                    "subscriber": sub.name,
                    "topics": sorted(sub.topics),
                    "mode": sub.mode,
                    "matched": len(matched),
                    "delivered": sum(1 for outcome in latest.values() if outcome.status == STATUS_OK),
                    "replayed": sum(1 for outcome in latest.values() if outcome.status == STATUS_REPLAYED),
                    "pending": len(pending),
                    "pending_seqs": pending[:10],
                    "attempts": sum(1 for outcome in outcomes if outcome.subscriber == sub.name),
                    "last_error": failures[-1].error if failures else None,
                }
            )
        return report

    def counts(self) -> dict[str, int]:
        """Return how many events were published per topic."""

        return dict(self._counter)

    def event_count(self) -> int:
        """Return how many events the durable log carries."""

        return len(self._log.events())

    def published(self) -> tuple[str, ...]:
        """Return the names of every published event in order."""

        return tuple(self._names)

    def _deliver(self, sub: Subscription, event: Event, *, replay: bool) -> str:
        attempt = 1 + sum(
            1
            for outcome in self._log.outcomes()
            if outcome.subscriber == sub.name and outcome.event_seq == event.seq
        )
        try:
            sub.handler(event)
        except Exception as exc:  # isolation boundary: one failure must not break the others
            self._log.append_outcome(
                Outcome(event.seq, sub.name, STATUS_FAILED, attempt, f"{type(exc).__name__}: {exc}")
            )
            return STATUS_FAILED
        status = STATUS_REPLAYED if replay else STATUS_OK
        self._log.append_outcome(Outcome(event.seq, sub.name, status, attempt))
        return status

    def _pending_events(self, sub: Subscription) -> list[Event]:
        latest: dict[int, str] = {}
        for outcome in self._log.outcomes():
            if outcome.subscriber == sub.name:
                latest[outcome.event_seq] = outcome.status
        return [
            event
            for event in self._log.events()
            if sub.matches(event.topic) and latest.get(event.seq) not in SETTLED
        ]

    def _one(self, subscriber: str) -> Subscription:
        for sub in self._subscriptions:
            if sub.name == subscriber:
                return sub
        raise NotFoundError("unknown subscriber", subscriber=subscriber)

    def _select(self, subscriber: str | None) -> tuple[Subscription, ...]:
        if subscriber is None:
            return tuple(self._subscriptions)
        return (self._one(subscriber),)
