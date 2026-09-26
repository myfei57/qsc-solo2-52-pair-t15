"""The journal codec round trips and refuses malformed lines."""

from __future__ import annotations

import pytest

from mixplant.errors import ValidationError
from mixplant.store.codec import ENTRY_APPEND, ENTRY_COMMIT, JournalEntry, decode_entry, encode_entry
from mixplant.store.records import Record


def test_append_entry_round_trips() -> None:
    record = Record.create(seq=1, kind="agg.weigh", origin="agg", generation=2, tick=3, payload={"active": True})
    entry = JournalEntry(entry_type=ENTRY_APPEND, tick=3, record=record)
    decoded = decode_entry(encode_entry(entry))
    assert decoded.record is not None
    assert decoded.record.kind == "agg.weigh"
    assert decoded.record.generation == 2


def test_commit_entry_round_trips() -> None:
    entry = JournalEntry(entry_type=ENTRY_COMMIT, tick=5, seq=4)
    assert decode_entry(encode_entry(entry)).seq == 4


def test_blank_line_is_refused() -> None:
    with pytest.raises(ValidationError):
        decode_entry("   ")


def test_record_kind_must_have_two_parts() -> None:
    with pytest.raises(ValidationError):
        Record.create(seq=1, kind="agg", origin="agg", generation=0, tick=0, payload={})
