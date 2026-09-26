"""Read models derived from the committed record stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..facts import derive_facts
from ..store.records import Record
from ..store.replay import state_at_tick
from ..store.repository import RecordRepository


@dataclass(frozen=True, slots=True)
class StateDelta:
    """The leaves that changed between an earlier tick and now."""

    tick: int
    now: int
    changed: tuple[str, ...]
    appeared: tuple[str, ...]
    disappeared: tuple[str, ...]

    def describe(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "now": self.now,
            "changed": list(self.changed),
            "appeared": list(self.appeared),
            "disappeared": list(self.disappeared),
        }


class StateView:
    """Answers the read questions the services and console ask."""

    __slots__ = ("_repository",)

    def __init__(self, repository: RecordRepository) -> None:
        self._repository = repository

    def current(self) -> dict[str, Any]:
        return self._repository.state()

    def as_of(self, tick: int) -> dict[str, Any]:
        return state_at_tick(self._repository.committed_records(), tick)

    def facts(self) -> dict[str, bool]:
        return derive_facts(self.current())

    def latest(self, kind: str) -> Record | None:
        return self._repository.latest(kind)

    def history(self, kind: str) -> tuple[Record, ...]:
        return self._repository.history(kind)

    def latest_payload(self, kind: str) -> Mapping[str, Any] | None:
        """Return the payload of the newest record of ``kind``."""

        record = self._repository.latest(kind)
        return None if record is None else record.payload

    def delta(self, tick: int) -> StateDelta:
        """Compare the state now with the state at ``tick``."""

        before = _leaves(self.as_of(tick))
        after = _leaves(self.current())
        changed = tuple(sorted(key for key in before.keys() & after.keys() if before[key] != after[key]))
        appeared = tuple(sorted(after.keys() - before.keys()))
        disappeared = tuple(sorted(before.keys() - after.keys()))
        return StateDelta(
            tick=tick,
            now=self._repository.watermark().tick,
            changed=changed,
            appeared=appeared,
            disappeared=disappeared,
        )


def _leaves(state: Mapping[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for group, leaves in state.items():
        if not isinstance(leaves, Mapping):
            flat[str(group)] = leaves
            continue
        for leaf, payload in leaves.items():
            flat[f"{group}.{leaf}"] = tuple(sorted(payload.items())) if isinstance(payload, Mapping) else payload
    return flat
