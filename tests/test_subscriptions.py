"""Per subscriber failure isolation, durable recovery and ordered replay."""

from __future__ import annotations

from mixplant.clock import ManualClock
from mixplant.event.bus import Event
from mixplant.event.durable import DurableEventBus
from mixplant.event.outbox import DELIVER_KIND, NOTIFY_KIND, REPLAY_KIND
from mixplant.ids import SequenceIds
from mixplant.store.repository import RecordRepository
from mixplant.runtime import PlantRuntime
from mixplant.config import StationConfig


class RecordingHandler:
    """A subscriber that can be told to fail on a given event sequence."""

    def __init__(
        self,
        name: str,
        *,
        failing: frozenset[int] | None = None,
        fail_first: bool = False,
    ) -> None:
        self.name = name
        self.failing = set(failing or ())
        self.fail_first = fail_first
        self._first_seen = False
        self.received: list[int] = []

    def __call__(self, event: Event) -> None:
        if self.fail_first and not self._first_seen:
            self._first_seen = True
            raise RuntimeError(f"{self.name} fails on its first event {event.seq}")
        if event.seq in self.failing:
            raise RuntimeError(f"{self.name} cannot handle {event.seq}")
        self.received.append(event.seq)

    def recover(self) -> None:
        """Stop failing the first event."""

        self.fail_first = False

    def heal(self, *seqs: int) -> None:
        for seq in seqs:
            self.failing.discard(seq)

    # Replayed deliveries hand the same event over again; adopt the boundary
    # the durable store already proved so an in memory handler stays
    # consistent with its checkpoint.
    def adopt_delivered(self, sequences: frozenset[int]) -> None:
        self.received = sorted(set(self.received) | set(sequences))


def bus():
    clock = ManualClock()
    ids = SequenceIds()
    store = RecordRepository.in_memory(clock, ids)
    return DurableEventBus(store, clock, ids), store


def notify_seqs(hub: DurableEventBus, name: str | None = None) -> list[int]:
    """Return committed notification sequences, optionally filtered by name."""

    records = hub._outbox.notifications()
    if name is None:
        return [record.seq for record in records]
    return [record.seq for record in records if record.payload["name"] == name]


def alarm_event(seq_name: str, *, origin: str = "agg", tick: int = 1, key: str | None = None) -> Event:
    payload = {} if key is None else {"key": key}
    return Event(topic="alarm", name=seq_name, origin=origin, tick=tick, payload=payload)


# -- 1. partial failure -------------------------------------------------------


def test_one_subscriber_failure_does_not_break_the_others() -> None:
    hub, _ = bus()
    good = RecordingHandler("good")
    bad = RecordingHandler("bad", failing=frozenset({1}))
    other = RecordingHandler("other")
    hub.register_durable("good", "alarm", good)
    hub.register_durable("bad", "alarm", bad)
    hub.register_durable("other", "mix", other)

    delivered = hub.publish(alarm_event("alarm.one"))

    # The first notification is the journal sequence; bad fails on seq 1.
    event_seq = notify_seqs(hub)[0]
    assert event_seq == 1
    assert delivered == 2
    assert good.received == [event_seq]
    assert bad.received == []
    assert hub.progress()["subscribers"]["bad"]["last_status"] == "failed"
    assert hub.backlog("bad") == 1
    assert hub.backlog("good") == 0
    # A non matching subscriber is unaffected too.
    assert other.received == []


def test_the_event_is_committed_even_when_a_subscriber_fails() -> None:
    hub, store = bus()
    hub.register_durable("bad", "alarm", RecordingHandler("bad", failing=frozenset({1})))
    hub.publish(alarm_event("alarm.one"))

    kinds = [record.kind for record in store.visible()]
    assert NOTIFY_KIND in kinds
    assert DELIVER_KIND in kinds


# -- 2. failure is durable and 3. restart replays in order --------------------


def test_backlog_survives_restart_and_replays_in_original_order(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    flaky = RecordingHandler("flaky", fail_first=True)
    first.bus.register_durable("flaky", "alarm", flaky)
    # The flaky subscriber only sees alarm events, whose notification
    # sequences are the first two journal rows after wiring.
    first.agg.raise_alarm("alarm.first")
    first.agg.raise_alarm("alarm.second")
    first_seq, second_seq = notify_seqs(first.bus)
    assert flaky.received == []
    assert first.bus.backlog("flaky") == 2
    first.close()

    second = PlantRuntime(config)
    healed = RecordingHandler("flaky", fail_first=True)
    second.bus.register_durable("flaky", "alarm", healed)
    report = second.bootstrap()
    second.bus.reload()
    # Restart rebuilds the cursor but does not silently replay.
    assert report["subscription_backlog"] == 2
    assert healed.received == []

    # The operator fixes the subscriber and explicitly catches up.
    healed.recover()
    replay = second.replay_subscriptions("flaky")
    assert replay["complete"] is True
    assert healed.received == [first_seq, second_seq]  # strict original order
    assert second.bus.backlog("flaky") == 0
    second.close()


# -- 3/5. replay is idempotent ------------------------------------------------


def test_replaying_twice_applies_each_event_once() -> None:
    hub, _ = bus()
    handler = RecordingHandler("h", failing=frozenset({1}))
    hub.register_durable("h", "alarm", handler)
    hub.publish(alarm_event("alarm.one"))
    hub.publish(alarm_event("alarm.two"))
    first_seq, second_seq = notify_seqs(hub)

    handler.heal(first_seq)
    first = hub.replay("h")
    second = hub.replay("h")

    # Sequential ordering held event 2 back while event 1 was open, so the
    # replay fills both in order; a second replay applies nothing and every
    # event is applied exactly once.
    assert first["delivered"] == 2
    assert first["reports"][0]["stopped_at"] is None
    assert second["delivered"] == 0
    assert handler.received == [first_seq, second_seq]
    assert len(handler.received) == len(set(handler.received))
    delivered_rows = [
        record
        for record in hub._outbox.deliveries()
        if record.subscriber == "h" and record.status == "delivered"
    ]
    event_seqs = [row.event_seq for row in delivered_rows]
    assert sorted(event_seqs) == sorted((first_seq, second_seq))
    assert len(event_seqs) == len(set(event_seqs))


# -- 4. sequential stops at the first gap -------------------------------------


def test_sequential_replay_stops_at_the_first_failure() -> None:
    hub, _ = bus()
    handler = RecordingHandler("seq", failing=frozenset({1}))
    hub.register_durable("seq", "alarm", handler, mode="sequential")
    hub.publish(alarm_event("a"))
    hub.publish(alarm_event("b"))
    hub.publish(alarm_event("c"))
    seqs = notify_seqs(hub)

    report = hub.replay("seq")

    assert report["complete"] is False
    assert report["reports"][0]["stopped_at"] == seqs[0]
    # It never jumped over the failing first event to reach later ones.
    assert handler.received == []
    assert hub.backlog("seq") == 3

    handler.heal(seqs[0])
    assert hub.replay("seq")["complete"] is True
    assert handler.received == seqs


# -- 4. a live event behind an open gap stays in the backlog ------------------


def test_live_delivery_never_overtakes_an_earlier_gap() -> None:
    hub, _ = bus()
    handler = RecordingHandler("seq", failing=frozenset({1}))
    hub.register_durable("seq", "alarm", handler, mode="sequential")
    hub.publish(alarm_event("a"))
    hub.publish(alarm_event("b"))
    seqs = notify_seqs(hub)

    # The second alarm must not have been applied before the first recovered.
    assert handler.received == []
    assert hub.backlog("seq") == 2

    handler.heal(seqs[0])
    report = hub.replay("seq")
    assert report["complete"] is True
    assert handler.received == seqs  # 1 before 2, never inverted


# -- 4. sharded replay fans out and preserves per key order -------------------


def test_sharded_replay_parallelises_but_keeps_each_shard_in_order() -> None:
    hub, _ = bus()
    handler = RecordingHandler("sh", failing=frozenset({1}))
    hub.register_durable(
        "sh",
        "alarm",
        handler,
        mode="sharded",
        shards=4,
        shard_key=lambda event: str(event.payload["key"]),
    )
    order = ["x", "y", "z", "x", "y"]
    for index, key in enumerate(order, start=1):
        hub.publish(alarm_event(f"alarm.{index}", tick=index, key=key))
    seqs = notify_seqs(hub)
    x_first, y_first, z_only, x_second, y_second = seqs

    # Live: x second is blocked behind the failed x first, while y/z advance.
    assert sorted(handler.received) == sorted((y_first, z_only, y_second))
    handler.heal(x_first)
    report = hub.replay("sh")

    assert report["complete"] is True
    assert report["reports"][0]["mode"] == "sharded"
    assert report["reports"][0]["shards"] == 4
    # Only the 'x' shard had a gap to replay, so one worker caught it up while
    # the y/z shards had already advanced independently during live delivery.
    assert report["reports"][0]["workers"] == 1
    # Every event applied exactly once and, within x, earlier before later.
    assert sorted(handler.received) == sorted(seqs)
    assert handler.received.index(x_first) < handler.received.index(x_second)
    assert handler.received.index(y_first) < handler.received.index(y_second)


def test_sharded_replay_one_shard_failing_does_not_block_others() -> None:
    hub, _ = bus()
    handler = RecordingHandler("sh", failing=frozenset({1}))
    hub.register_durable(
        "sh",
        "alarm",
        handler,
        mode="sharded",
        shards=4,
        shard_key=lambda event: str(event.payload["key"]),
    )
    hub.publish(alarm_event("a", tick=1, key="x"))
    hub.publish(alarm_event("b", tick=2, key="y"))
    x_seq, y_seq = notify_seqs(hub)

    report = hub.replay("sh")

    assert report["complete"] is False
    # The healthy shard still caught up; only the failing shard has backlog.
    assert y_seq in handler.received
    assert report["reports"][0]["stopped_at"] == x_seq
    assert hub.backlog("sh") == 1


# -- 8. progress is visible and every replay run is audited -------------------


def test_replay_writes_an_audit_summary_and_marks_replayed_rows() -> None:
    hub, store = bus()
    handler = RecordingHandler("h", failing=frozenset({1}))
    hub.register_durable("h", "alarm", handler)
    hub.publish(alarm_event("a"))
    only = notify_seqs(hub)[0]
    handler.heal(only)

    report = hub.replay("h")
    run_id = report["run_id"]

    progress = hub.progress()
    assert progress["subscribers"]["h"]["checkpoint"] == only
    assert progress["subscribers"]["h"]["replayed"] == 1
    assert progress["replay_runs"] == 1
    assert progress["last_run"]["run_id"] == run_id

    rows = [record for record in store.visible() if record.kind == REPLAY_KIND]
    assert len(rows) == 1
    assert list(rows[0].payload["subscribers"]) == ["h"]
    deliveries = [
        record
        for record in store.visible()
        if record.kind == DELIVER_KIND and record.payload["subscriber"] == "h"
    ]
    # One failed live attempt, one successful replay of the same event.
    statuses = {(row.payload["status"], row.payload["replayed"]) for row in deliveries}
    assert ("failed", False) in statuses
    assert ("delivered", True) in statuses


# -- 9. replay is foreground only ---------------------------------------------


def test_bootstrap_never_replays_silently(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    first.bus.register_durable("f", "alarm", RecordingHandler("f", fail_first=True))
    first.agg.raise_alarm("alarm.one")
    first.close()

    second = PlantRuntime(config)
    second.bootstrap()
    second.bus.register_durable("f", "alarm", RecordingHandler("f"))
    progress = second.subscription_progress()
    assert progress["policy"]["background_replay"] is False
    assert progress["policy"]["mode"] == "foreground"
    # The missed event is still waiting after boot; nothing was auto applied.
    assert second.bus.backlog("f") == 1
    second.close()


# -- built in subscribers are idempotent across replay ------------------------


def test_built_in_alarm_subscribers_do_not_duplicate_on_replay() -> None:
    runtime = PlantRuntime.in_memory()
    runtime.bootstrap()
    runtime.agg.raise_alarm("alarm.hot")
    alarms_before = runtime.alarms.count()
    ledger_before = len(runtime.audit.recent())

    # Replaying twice is a no op for already delivered alarms.
    runtime.replay_subscriptions("alarm.collector")
    runtime.replay_subscriptions("alarm.collector")
    runtime.replay_subscriptions("alarm.ledger")
    runtime.replay_subscriptions("alarm.ledger")

    assert runtime.alarms.count() == alarms_before
    assert len(runtime.audit.recent()) == ledger_before
    runtime.close()


def test_incomplete_replay_reports_the_gap_and_stays_visible() -> None:
    runtime = PlantRuntime.in_memory()
    runtime.bootstrap()
    always_broken = RecordingHandler("broken")
    always_broken.failing = set(range(1, 1_000_000))  # never recovers
    runtime.bus.register_durable("broken", "alarm", always_broken)
    runtime.agg.raise_alarm("alarm.x")

    response = runtime.replay_subscriptions("broken")
    assert response["complete"] is False
    assert response["reports"][0]["backlog_after"] == 1
    assert runtime.subscription_progress()["subscribers"]["broken"]["backlog"] == 1
    runtime.close()
