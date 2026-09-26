"""The truck queue: the order trucks are loaded in is the order they queued."""

from __future__ import annotations

from typing import Any

from ..errors import DuplicateError, NotFoundError, ValidationError


class TruckQueue:
    """A first in, first out queue of trucks waiting for concrete."""

    __slots__ = ("_waiting",)

    def __init__(self) -> None:
        self._waiting: list[str] = []

    def arrive(self, truck_id: str) -> int:
        """Append a truck and return its position, one based."""

        if not truck_id:
            raise ValidationError("truck identity must not be empty")
        if truck_id in self._waiting:
            raise DuplicateError("truck is already in the queue", truck_id=truck_id)
        self._waiting.append(truck_id)
        return len(self._waiting)

    def head(self) -> str:
        """Return the truck that must be served next."""

        if not self._waiting:
            raise NotFoundError("no truck is waiting for concrete")
        return self._waiting[0]

    def serve(self, truck_id: str) -> str:
        """Remove the head truck after confirming it is the one named."""

        head = self.head()
        if truck_id != head:
            raise ValidationError(
                "trucks must be loaded in the order they queued",
                expected=head,
                requested=truck_id,
                waiting=list(self._waiting),
            )
        self._waiting.pop(0)
        return truck_id

    def order(self) -> list[str]:
        return list(self._waiting)

    def waiting(self) -> int:
        return len(self._waiting)

    def describe(self) -> dict[str, Any]:
        return {"order": self.order(), "waiting": self.waiting()}
