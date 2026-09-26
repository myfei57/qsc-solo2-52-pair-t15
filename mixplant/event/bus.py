"""A synchronous publish and subscribe bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..errors import ValidationError
from .topics import TOPICS

Handler = Callable[["Event"], None]

ALL = "*"


@dataclass(frozen=True, slots=True)
class Event:
    """One notification raised by a service."""

    topic: str
    name: str
    origin: str
    tick: int
    payload: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def describe(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "name": self.name,
            "origin": self.origin,
            "tick": self.tick,
            "payload": dict(self.payload),
        }


class EventBus:
    """Delivers every event to the handlers registered for its topic."""

    __slots__ = ("_handlers", "_counter", "_names")

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self._counter: dict[str, int] = {}
        self._names: list[str] = []

    def subscribe(self, topic: str, handler: Handler) -> None:
        if not topic:
            raise ValidationError("subscription topic must not be empty")
        if topic != ALL and topic not in TOPICS:
            raise ValidationError("unknown topic", topic=topic)
        self._handlers.setdefault(topic, []).append(handler)

    def subscribe_all(self, handler: Handler) -> None:
        """Register a handler that sees every topic."""

        self.subscribe(ALL, handler)

    def handlers_for(self, topic: str) -> tuple[Handler, ...]:
        return tuple(self._handlers.get(topic, ())) + tuple(self._handlers.get(ALL, ()))

    def publish(self, event: Event) -> int:
        """Deliver ``event`` and return how many handlers ran."""

        if event.topic not in TOPICS:
            raise ValidationError("unknown topic", topic=event.topic)
        delivered = 0
        for handler in self.handlers_for(event.topic):
            handler(event)
            delivered += 1
        self._counter[event.topic] = self._counter.get(event.topic, 0) + 1
        self._names.append(event.name)
        return delivered

    def counts(self) -> dict[str, int]:
        """Return how many events were published per topic."""

        return dict(self._counter)

    def published(self) -> tuple[str, ...]:
        """Return the names of every published event in order."""

        return tuple(self._names)
