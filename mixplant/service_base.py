"""Plumbing shared by the plant services."""

from __future__ import annotations

from typing import Any, Mapping

from .context import SharedContext
from .errors import OrderViolationError
from .event.bus import Event
from .event.topics import ALARM, topic_for
from .statemachine.gate import GateResult
from .statemachine.machine import PhaseStep, SequenceMachine
from .store.records import Record
from .store.repository import RecordRepository


class PlantService:
    """Base class that keeps the write and event paths identical."""

    origin: str = ""
    line: str = ""
    subject: str = ""

    def __init__(self, context: SharedContext, machine: SequenceMachine | None = None) -> None:
        self.context = context
        self.machine = machine if machine is not None else SequenceMachine(self.line)

    @property
    def store(self) -> RecordRepository:
        return self.context.store

    def generation(self) -> int:
        """Return the generation that belongs to this service's subject."""

        if not self.subject:
            return 0
        return self.context.versions.current_generation(self.subject)

    def state(self) -> dict[str, Any]:
        return self.context.view.current()

    def facts(self, **extra: bool) -> dict[str, bool]:
        """Return the interlock facts, plus any service specific additions."""

        facts = self.context.view.facts()
        facts.update(extra)
        return facts

    def publish(self, kind: str, payload: Mapping[str, Any]) -> Record:
        """Append one committed record on behalf of this service."""

        body = dict(payload)
        body.setdefault("origin", self.origin)
        return self.store.publish(kind, self.origin, self.generation(), body)

    def emit(self, name: str, payload: Mapping[str, Any] | None = None) -> int:
        """Raise a domain event on the bus."""

        event = Event(
            topic=topic_for(self.origin),
            name=name,
            origin=self.origin,
            tick=self.context.clock.now(),
            payload=dict(payload or {}),
        )
        return self.context.bus.publish(event)

    def raise_alarm(self, name: str, payload: Mapping[str, Any] | None = None) -> int:
        """Raise an event on the alarm topic."""

        event = Event(
            topic=ALARM,
            name=name,
            origin=self.origin,
            tick=self.context.clock.now(),
            payload=dict(payload or {}),
        )
        return self.context.bus.publish(event)

    def require(self, action: str, *, required_phase: str | None = None, **extra: bool) -> GateResult:
        """Run the pre gate for ``action``."""

        return self.context.gate.require(
            action,
            facts=self.facts(**extra),
            machine=self.machine if required_phase is not None else None,
            required_phase=required_phase,
        )

    def advance(self, phase: str, reason: str) -> PhaseStep:
        """Move this service's line to the next stage."""

        step = self.machine.advance(phase, tick=self.context.clock.now(), reason=reason)
        self._record_phase(step)
        return step

    def rewind(self, phase: str, reason: str) -> PhaseStep:
        """Move this service's line back to an earlier stage."""

        step = self.machine.rewind_to(phase, tick=self.context.clock.now(), reason=reason)
        self._record_phase(step)
        return step

    def _record_phase(self, step: PhaseStep) -> None:
        """Persist the stage so a restart rebuilds the same machine."""

        self.publish(
            f"{self.line}.phase",
            {"active": True, "phase": step.phase, "step": step.step, "reason": step.reason},
        )

    def require_order(self, condition: bool, message: str, **context: Any) -> None:
        """Raise an order violation when ``condition`` is false."""

        if not condition:
            raise OrderViolationError(message, origin=self.origin, **context)

    def payload_entry(self, group: str, leaf: str) -> Mapping[str, Any] | None:
        """Return one derived leaf without the caller unpacking state."""

        node = self.state().get(group)
        if not isinstance(node, Mapping):
            return None
        entry = node.get(leaf)
        return entry if isinstance(entry, Mapping) else None
