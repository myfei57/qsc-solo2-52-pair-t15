"""Generation counters that make stale artifacts detectable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import StaleGenerationError, ValidationError


@dataclass(frozen=True, slots=True)
class GenerationToken:
    """One bump of a subject's generation."""

    subject: str
    value: int
    tick: int

    def describe(self) -> dict[str, Any]:
        return {"subject": self.subject, "value": self.value, "tick": self.tick}


class GenerationTracker:
    """Keeps the current generation of every subject that has one."""

    __slots__ = ("_current", "_history")

    def __init__(self) -> None:
        self._current: dict[str, int] = {}
        self._history: list[GenerationToken] = []

    def current(self, subject: str) -> int:
        """Return the generation a subject sits at, zero when unseen."""

        if not subject:
            raise ValidationError("subject must not be empty")
        return self._current.get(subject, 0)

    def bump(self, subject: str, *, tick: int) -> GenerationToken:
        """Raise a subject's generation and record the transition."""

        if not subject:
            raise ValidationError("subject must not be empty")
        token = GenerationToken(subject=subject, value=self.current(subject) + 1, tick=tick)
        self._current[subject] = token.value
        self._history.append(token)
        return token

    def require_current(self, subject: str, value: int, *, artifact: str) -> None:
        """Raise when ``value`` is not the subject's current generation."""

        current = self.current(subject)
        if value != current:
            raise StaleGenerationError(
                "artifact belongs to an older generation",
                artifact=artifact,
                subject=subject,
                artifact_generation=value,
                current_generation=current,
            )

    def adopt(self, subject: str, value: int) -> None:
        """Adopt a generation read back from the stream after a restart."""

        if value < 0:
            raise ValidationError("generation must not be negative", value=value)
        self._current[subject] = max(self.current(subject), value)

    def history(self) -> tuple[GenerationToken, ...]:
        return tuple(self._history)

    def subjects(self) -> tuple[str, ...]:
        return tuple(sorted(self._current))

    def describe(self) -> dict[str, int]:
        return dict(sorted(self._current.items()))
