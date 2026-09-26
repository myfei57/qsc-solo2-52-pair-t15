"""The per batch manifest of loads handed out."""

from __future__ import annotations

from typing import Any

from ..errors import DuplicateError, NotFoundError
from .load import LoadRecord


class LoadManifest:
    """Keeps which truck received which batch, and how much of it."""

    __slots__ = ("_loads",)

    def __init__(self) -> None:
        self._loads: dict[str, LoadRecord] = {}

    def record(self, load: LoadRecord) -> LoadRecord:
        if load.truck_id in self._loads:
            raise DuplicateError("truck already received a load", truck_id=load.truck_id)
        self._loads[load.truck_id] = load
        return load

    def require(self, truck_id: str) -> LoadRecord:
        load = self._loads.get(truck_id)
        if load is None:
            raise NotFoundError("truck never received a load", truck_id=truck_id)
        return load

    def for_batch(self, batch_id: str) -> tuple[LoadRecord, ...]:
        return tuple(load for load in self._loads.values() if load.batch_id == batch_id)

    def describe(self) -> dict[str, Any]:
        return {
            "loads": [load.describe() for load in self._loads.values()],
            "trucks": sorted(self._loads),
            "total_m3": round(sum(load.volume_m3 for load in self._loads.values()), 4),
        }
