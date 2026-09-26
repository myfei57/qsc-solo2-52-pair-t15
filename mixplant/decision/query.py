"""Filtering over the committed record stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..errors import ValidationError
from ..store.records import Record


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """The filter an audit or console read applies to the stream."""

    kind: str | None = None
    origin: str | None = None
    since_tick: int | None = None
    include_tombstones: bool = False
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValidationError("query limit must be positive", limit=self.limit)
        if self.since_tick is not None and self.since_tick < 0:
            raise ValidationError("query tick must not be negative", since_tick=self.since_tick)

    def matches(self, record: Record) -> bool:
        """Return whether ``record`` passes every condition."""

        if record.is_tombstone and not self.include_tombstones:
            return False
        if self.kind is not None and record.kind != self.kind:
            return False
        if self.origin is not None and record.origin != self.origin:
            return False
        if self.since_tick is not None and record.tick < self.since_tick:
            return False
        return True


@dataclass(frozen=True, slots=True)
class QueryResult:
    """The rows a query produced together with how many were skipped."""

    query: RecordQuery
    rows: tuple[Record, ...]
    matched: int

    def describe(self) -> dict[str, Any]:
        return {
            "kind": self.query.kind,
            "origin": self.query.origin,
            "include_tombstones": self.query.include_tombstones,
            "matched": self.matched,
            "returned": len(self.rows),
            "rows": [
                {
                    "seq": record.seq,
                    "kind": record.kind,
                    "origin": record.origin,
                    "generation": record.generation,
                    "tick": record.tick,
                    "tombstone_of": record.tombstone_of,
                    "payload": dict(record.payload),
                }
                for record in self.rows
            ],
        }


def run_query(records: Iterable[Record], query: RecordQuery) -> QueryResult:
    """Apply ``query`` to ``records`` and keep only the newest ``limit`` rows."""

    matched = [record for record in records if query.matches(record)]
    selected = matched if query.limit is None else matched[-query.limit :]
    return QueryResult(query=query, rows=tuple(selected), matched=len(matched))


def query_from_params(params: Mapping[str, Any]) -> RecordQuery:
    """Build a query from the loose string parameters a console supplies."""

    kind = params.get("kind")
    origin = params.get("origin")
    raw_limit = params.get("limit")
    raw_tick = params.get("since_tick")
    return RecordQuery(
        kind=str(kind) if kind else None,
        origin=str(origin) if origin else None,
        since_tick=None if raw_tick in (None, "") else int(raw_tick),
        include_tombstones=str(params.get("tombstones", "")).lower() in {"1", "true", "yes"},
        limit=None if raw_limit in (None, "") else int(raw_limit),
    )
