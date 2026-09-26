"""Combines a stage check with the interlock table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..errors import OrderViolationError
from .interlock import InterlockDecision, InterlockEngine
from .machine import SequenceMachine


@dataclass(frozen=True, slots=True)
class GateResult:
    """Everything the caller needs to explain an allow or a refusal."""

    action: str
    allowed: bool
    phase: str | None
    decision: InterlockDecision

    def describe(self) -> dict[str, object]:
        return {
            "action": self.action,
            "allowed": self.allowed,
            "phase": self.phase,
            "interlock": self.decision.describe(),
        }


class PreGate:
    """The single place a command is checked before it reaches a service."""

    __slots__ = ("_engine",)

    def __init__(self, engine: InterlockEngine) -> None:
        self._engine = engine

    @property
    def engine(self) -> InterlockEngine:
        return self._engine

    def evaluate(
        self,
        action: str,
        *,
        facts: Mapping[str, bool],
        machine: SequenceMachine | None = None,
        required_phase: str | None = None,
    ) -> GateResult:
        """Check the stage requirement and then the interlock table."""

        decision = self._engine.evaluate(action, facts)
        if machine is not None and required_phase is not None and decision.allowed:
            try:
                machine.require_at_least(required_phase, action=action)
            except OrderViolationError as exc:
                decision = InterlockDecision(
                    action=action,
                    allowed=False,
                    blocking=(f"stage:{required_phase}",),
                    missing=(str(exc.context.get("current", "")), required_phase),
                    message=exc.message,
                )
        return GateResult(
            action=action,
            allowed=decision.allowed,
            phase=None if machine is None else machine.phase,
            decision=decision,
        )

    def require(
        self,
        action: str,
        *,
        facts: Mapping[str, bool],
        machine: SequenceMachine | None = None,
        required_phase: str | None = None,
    ) -> GateResult:
        """Raise unless the gate would allow ``action``."""

        result = self.evaluate(action, facts=facts, machine=machine, required_phase=required_phase)
        if result.allowed:
            return result
        if result.decision.blocking and result.decision.blocking[0].startswith("stage:"):
            raise OrderViolationError(
                result.decision.message,
                action=action,
                required_phase=required_phase,
                phase=result.phase,
            )
        self._engine.require(action, facts)
        return result
