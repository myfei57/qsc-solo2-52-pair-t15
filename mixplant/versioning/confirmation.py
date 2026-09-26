"""Confirmations that hand a verified fact to a later stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import DuplicateError, NotFoundError
from .expiry import Validity


@dataclass(frozen=True, slots=True)
class Confirmation:
    """Proof that a subject was verified at a known tick."""

    confirmation_id: str
    subject: str
    generation: int
    issuer: str
    validity: Validity

    def is_expired(self, now: int) -> bool:
        return self.validity.is_expired(now)

    def require_fresh(self, now: int) -> None:
        self.validity.require_fresh(now, subject=f"confirmation:{self.subject}")

    def describe(self, now: int | None = None) -> dict[str, Any]:
        return {
            "confirmation_id": self.confirmation_id,
            "subject": self.subject,
            "generation": self.generation,
            "issuer": self.issuer,
            "validity": self.validity.describe(now),
        }


class ConfirmationRegistry:
    """Keeps the newest confirmation of every subject."""

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[str, Confirmation] = {}

    def record(self, confirmation: Confirmation) -> Confirmation:
        """Store ``confirmation`` unless its identity was already used."""

        for existing in self._entries.values():
            if existing.confirmation_id == confirmation.confirmation_id:
                raise DuplicateError(
                    "confirmation identity was reused", confirmation_id=confirmation.confirmation_id
                )
        self._entries[confirmation.subject] = confirmation
        return confirmation

    def latest(self, subject: str) -> Confirmation | None:
        return self._entries.get(subject)

    def require(self, subject: str) -> Confirmation:
        """Return the confirmation of ``subject`` or refuse the call."""

        confirmation = self.latest(subject)
        if confirmation is None:
            raise NotFoundError("subject was never confirmed", subject=subject)
        return confirmation

    def subjects(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def describe(self, now: int) -> dict[str, Any]:
        return {
            "subjects": list(self.subjects()),
            "entries": [entry.describe(now) for entry in self._entries.values()],
        }
