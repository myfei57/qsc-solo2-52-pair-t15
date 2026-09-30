"""A publish and subscribe bus that survives partial failure and restart.

Every *durable* subscriber owns an independent delivery cursor.  An event is
committed to the outbox first and then fanned out; when one subscriber raises
the exception is caught and recorded as that subscriber's failure while the
others still run and the publish still succeeds - a partial failure.

Failures never vanish: the missed event stays in that subscriber's backlog and
is delivered again by an explicit, *foreground* replay.  There is deliberately
no background retry thread; outstanding work is surfaced as backlog and the
operator decides when to catch up.  Replay follows the global event order:

* ``sequential`` subscribers are replayed one event at a time and stop at the
  first failure so their time order cannot move past a gap;
* ``sharded`` subscribers fan out over a thread pool by shard key; events for
  one key stay in order while different keys run in parallel.

Delivery and replay both write audit rows in the same committed journal the
events live in, which is what makes publication, recovery and audit agree.
Re-driving a replay is idempotent: an event a subscriber already handled is
skipped, never applied twice.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable

from ..clock import Clock
from ..errors import NotFoundError, ValidationError
from ..ids import SequenceIds
from ..store.repository import RecordRepository
from .bus import ALL, EventBus
from .outbox import (
    DELIVERED,
    FAILED,
    EventOutbox,
)

Handler = Callable[..., None]
ShardKey = Callable[[Any], str]


def _origin_shard(event: Any) -> str:
    return str(event.origin)


@dataclass(frozen=True, slots=True)
class Subscription:
    """One independently tracked subscriber."""

    name: str
    topic: str
    handler: Handler
    mode: str
    shard_key: ShardKey
    shards: int

    def accepts(self, topic: str) -> bool:
        return self.topic == ALL or self.topic == topic


@dataclass(slots=True)
class _Result:
    event_seq: int
    name: str
    status: str
    replayed: bool
    error: str = ""


class DurableEventBus(EventBus):
    """Fan out with per subscriber checkpoints and an auditable replay."""

    def __init__(self, store: RecordRepository, clock: Clock, ids: SequenceIds) -> None:
        super().__init__()
        self._outbox = EventOutbox(store, clock)
        self._ids = ids
        self._durable: dict[str, Subscription] = {}
        # Guards journal writes and the in memory handlers; one lock keeps the
        # committed delivery order identical to the order handlers ran in.
        self._lock = Lock()

    # -- registration -------------------------------------------------------

    def register_durable(
        self,
        name: str,
        topic: str,
        handler: Handler,
        *,
        mode: str = "sequential",
        shard_key: ShardKey | None = None,
        shards: int = 1,
    ) -> Subscription:
        """Track a subscriber by name and give it its own delivery cursor."""

        if not name:
            raise ValidationError("subscriber name must not be empty")
        if mode not in ("sequential", "sharded"):
            raise ValidationError("unknown replay mode", mode=mode, subscriber=name)
        if mode == "sharded" and shards < 2:
            raise ValidationError("a sharded subscriber needs at least two shards", subscriber=name)
        if name in self._durable:
            raise ValidationError("subscriber already registered", subscriber=name)
        subscription = Subscription(
            name=name,
            topic=topic,
            handler=handler,
            mode=mode,
            shard_key=shard_key or _origin_shard,
            shards=shards if mode == "sharded" else 1,
        )
        self._durable[name] = subscription
        return subscription

    def subscriber(self, name: str) -> Subscription:
        subscription = self._durable.get(name)
        if subscription is None:
            raise NotFoundError("unknown subscriber", subscriber=name)
        return subscription

    def subscriptions(self) -> tuple[Subscription, ...]:
        return tuple(self._durable.values())

    # -- restart ------------------------------------------------------------

    def reload(self) -> None:
        """Re seed every subscriber's idempotency memory after a restart."""

        for name, subscription in self._durable.items():
            hydrate = getattr(subscription.handler, "adopt_delivered", None)
            if callable(hydrate):
                hydrate(self._outbox.delivered_sequences(name))

    # -- live publish -------------------------------------------------------

    def publish(self, event: Any) -> int:
        """Commit the event, then deliver it without letting failures spread.

        Ephemeral handlers (plain ``subscribe``) run first for backwards
        compatibility.  Durable handlers are isolated: one raising only marks
        its own attempt failed.
        """

        ephemeral = [
            handler
            for handler in self.handlers_for(event.topic)
            if not self._is_durable_handler(handler)
        ]
        for handler in ephemeral:
            handler(event)

        with self._lock:
            record = self._outbox.publish_notification(event)
            stored = self._outbox.event_from_record(record)
            targets = [sub for sub in self._durable.values() if sub.accepts(stored.topic)]
            for subscription in targets:
                delivered = self._outbox.delivered_sequences(subscription.name)
                if self._is_behind(subscription, stored, delivered):
                    # An earlier event for this subscriber (or this shard) is
                    # still open.  Skip delivery so a later replay can fill the
                    # gap in original order instead of applying this one early.
                    continue
                self._attempt(subscription, stored, replayed=False)
        self._counter[event.topic] = self._counter.get(event.topic, 0) + 1
        self._names.append(event.name)
        return len(ephemeral) + len(targets)

    def _is_behind(
        self, subscription: Subscription, event: Any, delivered: frozenset[int]
    ) -> bool:
        """Return whether an earlier, not yet handled event blocks this one.

        Sequential subscribers are blocked by *any* earlier gap; sharded
        subscribers only by a gap on the same shard key, which is exactly what
        lets different shards make progress in parallel.
        """

        key = None if subscription.mode == "sequential" else str(subscription.shard_key(event))
        for record in self._outbox.notifications():
            if record.seq >= event.seq:
                break
            if record.seq in delivered or not subscription.accepts(str(record.payload["topic"])):
                continue
            if key is None:
                return True
            earlier = self._outbox.event_from_record(record)
            if str(subscription.shard_key(earlier)) == key:
                return True
        return False

    # -- replay -------------------------------------------------------------

    def replay(self, name: str | None = None) -> dict[str, Any]:
        """Catch one subscriber (or all of them) up, in the foreground."""

        names = (self.subscriber(name).name,) if name else tuple(self._durable)
        run_id = self._ids.next("replay")
        reports = [self._replay_one(self.subscriber(each)) for each in names]
        delivered = sum(item["delivered"] for item in reports)
        skipped = sum(item["skipped"] for item in reports)
        failed = sum(item["failed"] for item in reports)
        stopped = [item["stopped_at"] for item in reports if item["stopped_at"] is not None]
        complete = failed == 0 and not stopped
        summary = {
            "run_id": run_id,
            "subscribers": list(names),
            "delivered": delivered,
            "skipped": skipped,
            "failed": failed,
            "stopped_at": stopped[0] if stopped else None,
            "complete": complete,
            "mode": "foreground",
            "reports": reports,
        }
        with self._lock:
            self._outbox.record_replay(run_id, summary)
        return summary

    def _replay_one(self, subscription: Subscription) -> dict[str, Any]:
        already = self._outbox.delivered_sequences(subscription.name)
        pending = [
            record
            for record in self._outbox.notifications()
            if record.seq not in already
            and subscription.accepts(str(record.payload["topic"]))
        ]
        if subscription.mode == "sharded":
            return self._replay_sharded(subscription, pending)
        return self._replay_sequential(subscription, pending)

    def _replay_sequential(
        self, subscription: Subscription, pending: tuple[Any, ...]
    ) -> dict[str, Any]:
        # ``pending`` already excludes handled events, so a sequential replay
        # has nothing to skip; it walks the gap in strict global order and
        # stops at the first event still failing.
        delivered = failed = 0
        stopped_at: int | None = None
        for record in pending:
            event = self._outbox.event_from_record(record)
            result = self._guarded_attempt(subscription, event, replayed=True)
            if result.status == DELIVERED:
                delivered += 1
            else:
                failed += 1
                stopped_at = record.seq
                break
        return {
            "subscriber": subscription.name,
            "mode": "sequential",
            "delivered": delivered,
            "skipped": 0,
            "failed": failed,
            "stopped_at": stopped_at,
            "backlog_after": self.backlog(subscription.name),
        }

    def _replay_sharded(
        self, subscription: Subscription, pending: tuple[Any, ...]
    ) -> dict[str, Any]:
        buckets: dict[str, list[Any]] = {}
        for record in pending:
            event = self._outbox.event_from_record(record)
            key = subscription.shard_key(event)
            buckets.setdefault(str(key), []).append(record)

        workers = min(subscription.shards, max(1, len(buckets)))

        def drain(bucket: list[Any]) -> tuple[int, int, int | None]:
            # Each shard walks its own events in global order and never jumps
            # over a gap; different shards may advance independently.
            delivered = failed = 0
            stopped_at: int | None = None
            for record in sorted(bucket, key=lambda item: item.seq):
                event = self._outbox.event_from_record(record)
                result = self._guarded_attempt(subscription, event, replayed=True)
                if result.status == DELIVERED:
                    delivered += 1
                else:
                    failed += 1
                    stopped_at = record.seq
                    break
            return delivered, failed, stopped_at

        if workers == 1 or len(buckets) <= 1:
            outcomes = [drain(bucket) for bucket in buckets.values()]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                outcomes = list(pool.map(drain, list(buckets.values())))

        delivered = sum(item[0] for item in outcomes)
        failed = sum(item[1] for item in outcomes)
        stops = [item[2] for item in outcomes if item[2] is not None]

        return {
            "subscriber": subscription.name,
            "mode": "sharded",
            "shards": subscription.shards,
            "workers": workers,
            "delivered": delivered,
            "skipped": 0,
            "failed": failed,
            "stopped_at": min(stops) if stops else None,
            "backlog_after": self.backlog(subscription.name),
        }

    # -- delivery -----------------------------------------------------------

    def _guarded_attempt(self, subscription: Subscription, event: Any, *, replayed: bool) -> _Result:
        with self._lock:
            return self._attempt(subscription, event, replayed=replayed)

    def _attempt(self, subscription: Subscription, event: Any, *, replayed: bool) -> _Result:
        try:
            subscription.handler(event)
        except Exception as exc:  # partial failure: isolate this subscriber
            text = f"{type(exc).__name__}: {exc}"[:300]
            self._outbox.record_delivery(
                subscriber=subscription.name,
                event_seq=event.seq,
                status=FAILED,
                replayed=replayed,
                error=text,
            )
            return _Result(event.seq, subscription.name, FAILED, replayed, text)
        self._outbox.record_delivery(
            subscriber=subscription.name,
            event_seq=event.seq,
            status=DELIVERED,
            replayed=replayed,
        )
        return _Result(event.seq, subscription.name, DELIVERED, replayed)

    def _is_durable_handler(self, handler: Handler) -> bool:
        return any(subscription.handler == handler for subscription in self._durable.values())

    # -- progress -----------------------------------------------------------

    def checkpoint(self, name: str) -> int:
        """Return the highest event sequence a subscriber handled once."""

        self.subscriber(name)
        return max(self._outbox.delivered_sequences(name), default=0)

    def backlog(self, name: str) -> int:
        """Count surviving events a subscriber still has to handle."""

        subscription = self.subscriber(name)
        done = self._outbox.delivered_sequences(name)
        return sum(
            1
            for record in self._outbox.notifications()
            if record.seq not in done and subscription.accepts(str(record.payload["topic"]))
        )

    def progress(self) -> dict[str, Any]:
        """Describe every subscriber for the console and the health probe."""

        deliveries = self._outbox.deliveries()
        runs = self._outbox.replays()
        result: dict[str, Any] = {}
        for name, subscription in self._durable.items():
            attempts = [item for item in deliveries if item.subscriber == name]
            last = attempts[-1] if attempts else None
            result[name] = {
                "topic": subscription.topic,
                "mode": subscription.mode,
                "checkpoint": max(
                    (item.event_seq for item in attempts if item.status == DELIVERED), default=0
                ),
                "backlog": self.backlog(name),
                "delivered": sum(1 for item in attempts if item.status == DELIVERED),
                "failed": sum(1 for item in attempts if item.status == FAILED),
                "last_status": None if last is None else last.status,
                "last_event_seq": None if last is None else last.event_seq,
                "last_error": None if last is None or last.status != FAILED else last.error,
                "replayed": sum(
                    1
                    for item in attempts
                    if item.status == DELIVERED and item.replayed
                ),
            }
        return {
            "subscribers": result,
            "total_backlog": sum(item["backlog"] for item in result.values()),
            "replay_runs": len(runs),
            "last_run": None if not runs else self._describe_run(runs[-1]),
        }

    def replay_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the newest replay summaries, newest last."""

        runs = self._outbox.replays()
        return [self._describe_run(record) for record in runs[-limit:]]

    @staticmethod
    def _describe_run(record: Any) -> dict[str, Any]:
        payload = record.payload
        return {
            "seq": record.seq,
            "tick": record.tick,
            "run_id": payload.get("run_id"),
            "subscribers": list(payload.get("subscribers", ())),
            "delivered": payload.get("delivered", 0),
            "skipped": payload.get("skipped", 0),
            "failed": payload.get("failed", 0),
            "stopped_at": payload.get("stopped_at"),
            "complete": bool(payload.get("complete", False)),
            "mode": payload.get("mode", "foreground"),
        }
