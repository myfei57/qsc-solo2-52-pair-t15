"""A machine that only ever moves to the next declared stage."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import OrderViolationError, ValidationError
from .phases import sequence_for


@dataclass(frozen=True, slots=True)
class PhaseStep:
    """One accepted move of a line."""

    line: str
    phase: str
    step: int
    tick: int
    reason: str

    def describe(self) -> dict[str, object]:
        return {
            "line": self.line,
            "phase": self.phase,
            "step": self.step,
            "tick": self.tick,
            "reason": self.reason,
        }


class SequenceMachine:
    """Tracks which declared stage a line currently sits in."""

    __slots__ = ("_line", "_order", "_index", "_steps")

    def __init__(self, line: str) -> None:
        self._line = line
        self._order = sequence_for(line)
        self._index = 0
        self._steps: list[PhaseStep] = [
            PhaseStep(line=line, phase=self.phase, step=0, tick=0, reason="initial")
        ]

    @property
    def line(self) -> str:
        return self._line

    @property
    def phase(self) -> str:
        return str(self._order[self._index].value)

    @property
    def index(self) -> int:
        return self._index

    @property
    def last_step(self) -> PhaseStep:
        return self._steps[-1]

    def order(self) -> tuple[str, ...]:
        """Return every declared stage in order."""

        return tuple(str(phase.value) for phase in self._order)

    def history(self) -> tuple[PhaseStep, ...]:
        return tuple(self._steps)

    def is_at(self, phase: str) -> bool:
        return self.phase == phase

    def is_at_least(self, phase: str) -> bool:
        return self._index >= self._index_of(phase)

    def next_phase(self) -> str | None:
        """Return the only stage this line may move to next."""

        if self._index + 1 >= len(self._order):
            return None
        return str(self._order[self._index + 1].value)

    def _index_of(self, phase: str) -> int:
        for index, candidate in enumerate(self._order):
            if str(candidate.value) == phase:
                return index
        raise ValidationError("stage is not part of this line", line=self._line, phase=phase)

    def advance(self, phase: str, *, tick: int, reason: str) -> PhaseStep:
        """Move to the next stage or refuse with an order violation."""

        upcoming = self.next_phase()
        if upcoming is None:
            raise OrderViolationError(
                "line already sits in its final stage",
                line=self._line,
                phase=self.phase,
                requested=phase,
            )
        if phase != upcoming:
            raise OrderViolationError(
                "stage was requested out of order",
                line=self._line,
                current=self.phase,
                expected=upcoming,
                requested=phase,
            )
        self._index += 1
        step = PhaseStep(line=self._line, phase=phase, step=self._index, tick=tick, reason=reason)
        self._steps.append(step)
        return step

    def require_at_least(self, phase: str, *, action: str) -> None:
        """Refuse ``action`` when the line has not reached ``phase`` yet."""

        required = self._index_of(phase)
        if self._index < required:
            raise OrderViolationError(
                "action needs an earlier stage to have completed",
                line=self._line,
                action=action,
                current=self.phase,
                required=phase,
            )

    def rewind_to(self, phase: str, *, tick: int, reason: str) -> PhaseStep:
        """Move the line back to an earlier stage, never forwards."""

        index = self._index_of(phase)
        if index > self._index:
            raise OrderViolationError(
                "rewind can only move a line backwards",
                line=self._line,
                current=self.phase,
                requested=phase,
            )
        self._index = index
        step = PhaseStep(line=self._line, phase=phase, step=index, tick=tick, reason=reason)
        self._steps.append(step)
        return step

    def hydrate(self, phase: str, *, step: int, tick: int) -> None:
        """Adopt a stage read back from the stream after a restart."""

        index = self._index_of(phase)
        if step < index:
            raise OrderViolationError(
                "replayed step is behind the stage it names",
                line=self._line,
                phase=phase,
                step=step,
            )
        self._index = index
        self._steps = [PhaseStep(line=self._line, phase=phase, step=step, tick=tick, reason="hydrated")]
