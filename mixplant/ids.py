"""Deterministic identifier factory.

Identifiers are derived from per-scope counters instead of randomness so that
two runs of the same command sequence produce byte identical journals.
"""

from __future__ import annotations

from .errors import ValidationError


class SequenceIds:
    """Hands out ``scope-000001`` style identifiers."""

    __slots__ = ("_width", "_start", "_counters")

    def __init__(self, width: int = 6, start: int = 0) -> None:
        if width < 1:
            raise ValueError("width must be positive")
        if start < 0:
            raise ValueError("start must not be negative")
        self._width = width
        self._start = start
        self._counters: dict[str, int] = {}

    def next(self, scope: str) -> str:
        """Return the next identifier for ``scope``."""

        if not scope:
            raise ValidationError("identifier scope must not be empty")
        value = self._counters.get(scope, self._start) + 1
        self._counters[scope] = value
        return f"{scope}-{value:0{self._width}d}"

    def issued(self, scope: str) -> int:
        """Return how many identifiers ``scope`` has handed out."""

        return self._counters.get(scope, self._start)

    def restore(self, scope: str, count: int) -> None:
        """Raise a scope counter after a restart so ids stay unique."""

        if count < 0:
            raise ValueError("issued count must not be negative")
        self._counters[scope] = max(self._counters.get(scope, self._start), self._start + count)
