"""Validity windows attached to confirmations, baselines and snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import ValidationError

NEVER = -1


@dataclass(frozen=True, slots=True)
class Validity:
    """A window that starts at ``issued`` and expires after ``ttl`` ticks."""

    issued: int
    ttl: int

    def __post_init__(self) -> None:
        if self.issued < 0:
            raise ValidationError("validity must start at a non negative tick", issued=self.issued)
        if self.ttl < NEVER:
            raise ValidationError("validity ttl must be -1 or a non negative number", ttl=self.ttl)

    @classmethod
    def of(cls, issued: int, ttl: int) -> "Validity":
        return cls(issued=issued, ttl=ttl)

    @classmethod
    def never(cls, issued: int) -> "Validity":
        """Return a window that never expires."""

        return cls(issued=issued, ttl=NEVER)

    @property
    def open_ended(self) -> bool:
        return self.ttl == NEVER

    def valid_until(self) -> int | None:
        return None if self.open_ended else self.issued + self.ttl

    def is_expired(self, now: int) -> bool:
        if self.open_ended:
            return False
        return now > self.issued + self.ttl

    def remaining(self, now: int) -> int:
        """Return how many ticks are left, or -1 for an open ended window."""

        if self.open_ended:
            return NEVER
        return max(0, self.issued + self.ttl - now)

    def require_fresh(self, now: int, *, subject: str) -> None:
        """Raise ``ArtifactExpiredError`` when the window has closed."""

        from ..errors import ArtifactExpiredError

        if self.is_expired(now):
            raise ArtifactExpiredError(
                "artifact is past its validity window",
                subject=subject,
                issued=self.issued,
                ttl=self.ttl,
                now=now,
            )

    def describe(self, now: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "issued": self.issued,
            "ttl": self.ttl,
            "valid_until": self.valid_until(),
        }
        if now is not None:
            payload["remaining"] = self.remaining(now)
            payload["expired"] = self.is_expired(now)
        return payload

    def to_document(self) -> dict[str, int]:
        return {"issued": self.issued, "ttl": self.ttl}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Validity":
        return cls(issued=int(document["issued"]), ttl=int(document["ttl"]))
