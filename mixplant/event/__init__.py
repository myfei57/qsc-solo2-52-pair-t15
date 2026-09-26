"""Synchronous event plumbing shared by the services."""

from __future__ import annotations

from .bus import ALL, Event, EventBus
from .topics import TOPICS, topic_for

__all__ = ["ALL", "Event", "EventBus", "TOPICS", "topic_for"]
