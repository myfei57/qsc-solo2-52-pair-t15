"""The record model of the append only stream."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..errors import ValidationError

KIND_SEPARATOR = "."


def freeze_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return an immutable copy of ``payload``."""

    return MappingProxyType(dict(payload))


@dataclass(frozen=True, slots=True)
class Record:
    """One entry of the append only stream.

    ``kind`` always has the shape ``<group>.<leaf>`` so a replayed state
    mapping can be built without a registry of special cases.
    """

    seq: int
    kind: str
    origin: str
    generation: int
    tick: int
    payload: Mapping[str, Any]
    tombstone_of: int | None = None

    def __post_init__(self) -> None:
        if self.seq < 1:
            raise ValidationError("record sequence starts at one", seq=self.seq)
        if self.kind.count(KIND_SEPARATOR) != 1:
            raise ValidationError("record kind must look like '<group>.<leaf>'", kind=self.kind)
        group, leaf = self.kind.split(KIND_SEPARATOR)
        if not group or not leaf:
            raise ValidationError("record kind parts must not be empty", kind=self.kind)
        if not self.origin:
            raise ValidationError("record origin must not be empty")
        if self.generation < 0:
            raise ValidationError("record generation must not be negative", generation=self.generation)
        if self.tick < 0:
            raise ValidationError("record tick must not be negative", tick=self.tick)
        if self.tombstone_of is not None and self.tombstone_of >= self.seq:
            raise ValidationError(
                "a tombstone can only reference an earlier sequence",
                tombstone_of=self.tombstone_of,
                seq=self.seq,
            )

    @property
    def is_tombstone(self) -> bool:
        return self.tombstone_of is not None

    @property
    def group(self) -> str:
        return self.kind.split(KIND_SEPARATOR)[0]

    @property
    def leaf(self) -> str:
        return self.kind.split(KIND_SEPARATOR)[1]

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "seq": self.seq,
            "kind": self.kind,
            "origin": self.origin,
            "generation": self.generation,
            "tick": self.tick,
            "payload": dict(self.payload),
        }
        if self.tombstone_of is not None:
            document["tombstone_of"] = self.tombstone_of
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Record":
        payload = document.get("payload") or {}
        if not isinstance(payload, Mapping):
            raise ValidationError("record payload must be a mapping", seq=document.get("seq"))
        raw_tombstone = document.get("tombstone_of")
        return cls(
            seq=int(document["seq"]),
            kind=str(document["kind"]),
            origin=str(document["origin"]),
            generation=int(document["generation"]),
            tick=int(document["tick"]),
            payload=freeze_payload(payload),
            tombstone_of=None if raw_tombstone is None else int(raw_tombstone),
        )

    @classmethod
    def create(
        cls,
        *,
        seq: int,
        kind: str,
        origin: str,
        generation: int,
        tick: int,
        payload: Mapping[str, Any],
        tombstone_of: int | None = None,
    ) -> "Record":
        return cls(
            seq=seq,
            kind=kind,
            origin=origin,
            generation=generation,
            tick=tick,
            payload=freeze_payload(payload),
            tombstone_of=tombstone_of,
        )


TOMBSTONE_KIND = "store.tombstone"
