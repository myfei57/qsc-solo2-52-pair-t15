"""Line codec for the journal file.

The journal stores three entry types.  ``append`` carries a record while
``durable`` and ``commit`` carry a watermark.  Keeping them apart is what
lets a restart tell "written but not flushed" from "flushed but not
committed".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from ..errors import ValidationError
from .records import Record

ENTRY_APPEND = "append"
ENTRY_DURABLE = "durable"
ENTRY_COMMIT = "commit"
ENTRY_TYPES = (ENTRY_APPEND, ENTRY_DURABLE, ENTRY_COMMIT)


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One durable line of the journal."""

    entry_type: str
    tick: int
    record: Record | None = None
    seq: int | None = None
    detail: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if self.entry_type not in ENTRY_TYPES:
            raise ValidationError("unknown journal entry type", entry_type=self.entry_type)
        if self.entry_type == ENTRY_APPEND and self.record is None:
            raise ValidationError("append entries must carry a record")
        if self.entry_type != ENTRY_APPEND and self.seq is None:
            raise ValidationError("watermark entries must carry a sequence", entry_type=self.entry_type)

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {"type": self.entry_type, "tick": self.tick}
        if self.record is not None:
            document["record"] = self.record.to_document()
        if self.seq is not None:
            document["seq"] = self.seq
        if self.detail:
            document["detail"] = dict(self.detail)
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "JournalEntry":
        entry_type = str(document.get("type", ""))
        raw_record = document.get("record")
        record = Record.from_document(raw_record) if isinstance(raw_record, Mapping) else None
        raw_seq = document.get("seq")
        detail = document.get("detail") or {}
        if not isinstance(detail, Mapping):
            raise ValidationError("journal entry detail must be a mapping")
        return cls(
            entry_type=entry_type,
            tick=int(document.get("tick", 0)),
            record=record,
            seq=None if raw_seq is None else int(raw_seq),
            detail=MappingProxyType(dict(detail)),
        )


def encode_entry(entry: JournalEntry) -> str:
    """Serialise ``entry`` to exactly one deterministic line."""

    return json.dumps(entry.to_document(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def decode_entry(line: str) -> JournalEntry:
    """Parse a single journal line."""

    text = line.strip()
    if not text:
        raise ValidationError("journal line must not be blank")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError("journal line is not valid json", line=text[:64]) from exc
    if not isinstance(document, Mapping):
        raise ValidationError("journal line must decode to an object")
    return JournalEntry.from_document(document)
