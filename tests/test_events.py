"""The event bus, its topics and its subscribers."""

from __future__ import annotations

import pytest

from mixplant.clock import ManualClock
from mixplant.errors import ValidationError
from mixplant.event.bus import ALL, Event, EventBus
from mixplant.event.subscribers import AlarmCollector, AuditSubscriber
from mixplant.event.topics import ALARM, TOPICS, topic_for
from mixplant.ids import SequenceIds
from mixplant.store.repository import RecordRepository


def test_topics_map_origins() -> None:
    assert topic_for("agg") == "agg"
    assert "sampler" in TOPICS
    with pytest.raises(ValidationError):
        topic_for("missing")


def test_bus_delivers_to_topic_and_wildcard_handlers() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe("agg", lambda event: seen.append("topic"))
    bus.subscribe_all(lambda event: seen.append("all"))
    delivered = bus.publish(Event(topic="agg", name="agg.weighed", origin="agg", tick=1))
    assert delivered == 2
    assert seen == ["topic", "all"]
    assert bus.published() == ("agg.weighed",)
    assert bus.handlers_for(ALL) != ()


def test_unknown_topics_are_refused() -> None:
    bus = EventBus()
    with pytest.raises(ValidationError):
        bus.subscribe("missing", lambda event: None)


def test_audit_subscriber_copies_events_into_the_stream() -> None:
    store = RecordRepository.in_memory(ManualClock(), SequenceIds())
    subscriber = AuditSubscriber(store)
    subscriber(Event(topic="mix", name="mix.started", origin="mix", tick=2))
    assert subscriber.seen() == 1
    assert store.visible()[0].kind == "audit.event"


def test_alarm_collector_keeps_only_alarm_events() -> None:
    collector = AlarmCollector(capacity=2)
    collector(Event(topic="mix", name="mix.started", origin="mix", tick=1))
    for index in range(3):
        collector(Event(topic=ALARM, name=f"alarm-{index}", origin="agg", tick=index))
    assert collector.count() == 2
    assert [entry["name"] for entry in collector.recent()] == ["alarm-1", "alarm-2"]
    collector.clear()
    assert collector.count() == 0
