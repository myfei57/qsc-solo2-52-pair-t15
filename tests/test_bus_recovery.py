"""Delivery isolation, durable failure bookkeeping and foreground replay."""

from __future__ import annotations

import json

import pytest

from mixplant.config import StationConfig
from mixplant.console.pages import PageStore
from mixplant.console.router import Request
from mixplant.console.server import ConsoleServer
from mixplant.errors import NotFoundError, ValidationError
from mixplant.event.bus import Event, EventBus
from mixplant.event.delivery import (
    BUS_DELIVERY_KIND,
    BUS_EVENT_KIND,
    BUS_REPLAY_KIND,
    MemoryDeliveryLog,
    ReplayMode,
)
from mixplant.event.subscribers import AUDIT_KIND, AuditSubscriber
from mixplant.event.topics import ALARM
from mixplant.ids import SequenceIds
from mixplant.clock import ManualClock
from mixplant.runtime import PlantRuntime
from mixplant.store.repository import RecordRepository


class Flaky:
    """A handler that is down while ``down`` and poisons named events."""

    def __init__(self) -> None:
        self.down = False
        self.poison: set[str] = set()
        self.seen: list[str] = []

    def __call__(self, event: Event) -> None:
        if self.down or event.name in self.poison:
            raise RuntimeError(f"cannot handle {event.name}")
        self.seen.append(event.name)


def alarm(name: str, **payload: object) -> Event:
    return Event(topic=ALARM, name=name, origin="agg", tick=1, payload=payload)


def test_one_subscriber_failing_never_breaks_the_others() -> None:
    bus = EventBus()
    flaky = Flaky()
    flaky.down = True
    ok_seen: list[str] = []
    bus.subscribe(ALARM, flaky, name="flaky")
    bus.subscribe(ALARM, lambda event: ok_seen.append(event.name), name="ok")

    delivered = bus.publish(alarm("a1"))

    assert delivered == 1  # the healthy subscriber still got the event
    assert ok_seen == ["a1"]
    assert bus.published() == ("a1",)
    assert bus.pending("flaky") != ()
    assert bus.pending("ok") == ()


def test_publish_raises_nothing_when_a_subscriber_fails() -> None:
    bus = EventBus()
    flaky = Flaky()
    flaky.down = True
    bus.subscribe(ALARM, flaky, name="flaky")
    assert bus.publish(alarm("a1")) == 0


def test_failed_deliveries_are_journaled_with_the_error() -> None:
    log = MemoryDeliveryLog()
    bus = EventBus(log)
    flaky = Flaky()
    flaky.down = True
    bus.subscribe(ALARM, flaky, name="flaky")
    bus.publish(alarm("a1"))
    outcomes = log.outcomes()
    assert [outcome.status for outcome in outcomes] == ["failed"]
    assert "a1" in (outcomes[0].error or "")
    assert log.events()[0].seq == 1


def test_replay_recovers_in_publish_order_and_marks_what_it_caught_up() -> None:
    bus = EventBus()
    flaky = Flaky()
    bus.subscribe(ALARM, flaky, name="flaky")
    flaky.down = True
    for name in ("a1", "a2", "a3"):
        bus.publish(alarm(name))
    assert flaky.seen == []

    flaky.down = False
    report = bus.replay()

    assert flaky.seen == ["a1", "a2", "a3"]  # original order, one by one
    assert report["flaky"]["recovered"] == 3
    assert report["flaky"]["pending_after"] == 0
    progress = bus.progress()[0]
    assert progress["replayed"] == 3
    assert progress["pending"] == 0


def test_replay_is_idempotent_when_triggered_repeatedly() -> None:
    log = MemoryDeliveryLog()
    bus = EventBus(log)
    flaky = Flaky()
    bus.subscribe(ALARM, flaky, name="flaky")
    flaky.down = True
    bus.publish(alarm("a1"))
    flaky.down = False

    first = bus.replay()
    outcomes_after_first = len(log.outcomes())
    replays_after_first = len(log.replays())
    second = bus.replay()
    third = bus.replay("flaky")

    assert first["flaky"]["recovered"] == 1
    assert second["flaky"]["attempted"] == 0
    assert third["flaky"]["attempted"] == 0
    assert flaky.seen == ["a1"]  # never delivered twice
    assert len(log.outcomes()) == outcomes_after_first
    assert len(log.replays()) == replays_after_first


def test_sequential_replay_stops_at_the_first_failure() -> None:
    bus = EventBus()
    flaky = Flaky()
    bus.subscribe(ALARM, flaky, name="flaky")
    flaky.down = True
    for name in ("a1", "a2", "a3"):
        bus.publish(alarm(name))
    flaky.down = False
    flaky.poison.add("a2")

    report = bus.replay()

    assert flaky.seen == ["a1"]  # a3 must not overtake the failed a2
    assert report["flaky"]["recovered"] == 1
    assert len(bus.pending("flaky")) == 2

    flaky.poison.clear()
    bus.replay()
    assert flaky.seen == ["a1", "a2", "a3"]
    assert bus.pending("flaky") == ()


def test_sharded_replay_keeps_lanes_independent_and_ordered() -> None:
    bus = EventBus()
    flaky = Flaky()
    bus.subscribe(
        ALARM,
        flaky,
        name="flaky",
        mode=ReplayMode.SHARDED,
        shard_of=lambda event: str(event.payload["lane"]),
    )
    flaky.down = True
    bus.publish(alarm("a1", lane="a"))
    bus.publish(alarm("b1", lane="b"))
    bus.publish(alarm("a2", lane="a"))
    bus.publish(alarm("b2", lane="b"))
    bus.publish(alarm("a3", lane="a"))
    flaky.down = False
    flaky.poison.add("a2")

    report = bus.replay()

    assert flaky.seen == ["a1", "b1", "b2"]  # lane b finished although lane a jammed
    assert report["flaky"]["lanes"] == {"a": 1, "b": 2}
    assert len(bus.pending("flaky")) == 2  # a2 and the a3 queued behind it

    flaky.poison.clear()
    bus.replay()
    assert flaky.seen[-2:] == ["a2", "a3"]  # lane a keeps its temporal order
    assert bus.pending("flaky") == ()


def test_sharded_subscription_requires_a_shard_key() -> None:
    bus = EventBus()
    with pytest.raises(ValidationError):
        bus.subscribe(ALARM, lambda event: None, mode=ReplayMode.SHARDED)
    with pytest.raises(ValidationError):
        bus.subscribe(ALARM, lambda event: None, shard_of=lambda event: "x")
    with pytest.raises(ValidationError):
        bus.subscribe(ALARM, lambda event: None, mode="sideways")


def test_replay_of_an_unknown_subscriber_is_refused() -> None:
    bus = EventBus()
    with pytest.raises(NotFoundError):
        bus.replay("missing")
    with pytest.raises(NotFoundError):
        bus.pending("missing")


def test_audit_subscriber_skips_events_it_already_copied() -> None:
    store = RecordRepository.in_memory(ManualClock(), SequenceIds())
    subscriber = AuditSubscriber(store)
    event = Event(topic="mix", name="mix.started", origin="mix", tick=2, seq=7)
    subscriber(event)
    subscriber(event)  # a repeated replay attempt must not copy twice
    assert subscriber.seen() == 1
    assert len(store.history(AUDIT_KIND)) == 1

    revived = AuditSubscriber(store)
    revived.hydrate(store.history(AUDIT_KIND))
    revived(event)
    assert revived.seen() == 0
    assert len(store.history(AUDIT_KIND)) == 1


def test_restart_replays_what_a_subscriber_missed(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    received: list[str] = []
    first.bus.subscribe(ALARM, Flaky(), name="flaky")
    flaky = first.bus.subscriptions()[-1].handler
    assert isinstance(flaky, Flaky)
    flaky.down = True
    for name in ("a1", "a2", "a3"):
        first.bus.publish(alarm(name))
    assert first.health()["bus_pending"] == 3
    first.close()

    second = PlantRuntime(config)
    fixed = Flaky()
    received = fixed.seen
    second.bus.subscribe(ALARM, fixed, name="flaky")
    report = second.bootstrap()

    assert received == ["a1", "a2", "a3"]  # caught up in the original order
    assert report["bus_recovery"]["flaky"]["recovered"] == 3
    assert second.health()["bus_pending"] == 0
    progress = {item["subscriber"]: item for item in second.bus.progress()}
    assert progress["flaky"]["replayed"] == 3
    assert progress["flaky"]["pending"] == 0

    seq_before = second.store.last_seq()
    again = second.bus.replay()  # a repeated trigger is a no-op, even in the journal
    assert all(item["attempted"] == 0 for item in again.values())
    assert second.store.last_seq() == seq_before
    second.close()


def test_delivery_replay_and_audit_tell_one_story(tmp_path) -> None:
    config = StationConfig(data_dir=tmp_path / "state")
    first = PlantRuntime(config)
    first.bootstrap()
    flaky = Flaky()
    flaky.down = True
    first.bus.subscribe(ALARM, flaky, name="flaky")
    first.bus.publish(alarm("a1"))
    first.bus.publish(alarm("a2"))
    first.close()

    second = PlantRuntime(config)
    second.bus.subscribe(ALARM, Flaky(), name="flaky")
    second.bootstrap()

    deliveries = second.records({"kind": BUS_DELIVERY_KIND})["rows"]
    flaky_rows = [row for row in deliveries if row["payload"]["subscriber"] == "flaky"]
    statuses = [row["payload"]["status"] for row in flaky_rows]
    assert statuses == ["failed", "failed", "replayed", "replayed"]
    replays = second.records({"kind": BUS_REPLAY_KIND})["rows"]
    assert replays[-1]["payload"]["recovered"] == 2
    events = second.records({"kind": BUS_EVENT_KIND})["rows"]
    assert len(events) == 2  # journaled before delivery, so nothing was lost
    second.close()


def test_console_exposes_progress_and_triggers_replay(runtime: PlantRuntime) -> None:
    server = ConsoleServer(runtime, pages=PageStore(runtime.config.web_dir))
    flaky = Flaky()
    flaky.down = True
    runtime.bus.subscribe(ALARM, flaky, name="flaky")
    runtime.bus.publish(alarm("a1"))

    status = server.handle(Request(method="GET", path="/api/bus"))
    assert status.ok is True
    body = json.loads(status.text)
    assert body["pending"] == 1
    entry = {item["subscriber"]: item for item in body["subscribers"]}["flaky"]
    assert entry["mode"] == "sequential"
    assert entry["pending"] == 1
    assert entry["last_error"] is not None

    flaky.down = False
    replayed = server.handle(Request(method="POST", path="/api/bus/replay", body={"subscriber": "flaky"}))
    assert replayed.ok is True
    assert json.loads(replayed.text)["result"]["flaky"]["recovered"] == 1
    assert json.loads(server.handle(Request(method="GET", path="/api/bus")).text)["pending"] == 0

    missing = server.handle(Request(method="POST", path="/api/bus/replay", body={"subscriber": "missing"}))
    assert missing.status == 404


def test_state_and_health_carry_the_bus_position(runtime: PlantRuntime) -> None:
    state = runtime.state()
    assert {item["subscriber"] for item in state["bus"]} == {
        "alarm-collector",
        "audit-ledger",
        "audit-stream",
    }
    assert runtime.health()["bus_pending"] == 0
