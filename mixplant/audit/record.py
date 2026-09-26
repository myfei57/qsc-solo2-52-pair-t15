"""One audited production event."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """A named production event kept for the shift ledger."""

    name: str
    origin: str
    tick: int
    detail: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("an audit entry needs a name")
        if not self.origin:
            raise ValidationError("an audit entry needs an origin", name=self.name)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "name": self.name, "origin": self.origin, "tick": self.tick, "detail": dict(self.detail)}


def audit_entry(*, name: str, origin: str, tick: int, detail: dict[str, Any] | None = None) -> AuditEntry:
    """Build one audit entry."""

    return AuditEntry(name=name, origin=origin, tick=tick, detail=dict(detail or {}))
