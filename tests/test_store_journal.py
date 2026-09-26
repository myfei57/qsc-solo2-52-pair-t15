"""The record stream is append only, watermarked and restorable."""

from __future__ import annotations

import pytest

from mixplant.clock import ManualClock
from mixplant.errors import RecordError, UnknownRecordError
from mixplant.ids import SequenceIds
from mixplant.store.codec import JournalEntry
from mixplant.store.journal import MemoryBackend
from mixplant.store.repository import RecordRepository
from mixplant.versioning.expiry import Validity


def _repository() -> RecordRepository:
    return RecordRepository.in_memory(ManualClock(), SequenceIds())


def test_staged_records_are_not_visible_until_flushed() -> None:
    store = _repository()
    store.stage("agg.weigh", "agg", 1, {"active": True})
    assert store.staged_records()
    assert store.visible() == ()
    store.flush()
    store.commit()
    assert len(store.visible()) == 1


def test_publish_moves_both_watermarks() -> None:
    store = _repository()
    record = store.publish("agg.weigh", "agg", 1, {"active": True})
    watermark = store.watermark()
    assert watermark.committed_seq == record.seq
    assert watermark.durable_seq == record.seq


def test_commit_never_moves_backwards() -> None:
    store = _repository()
    store.publish("agg.weigh", "agg", 1, {"active": True})
    second = store.publish("agg.persist", "agg", 1, {"active": True})
    with pytest.raises(RecordError):
        store.commit_through(second.seq - 2)


def test_rollback_hides_later_records() -> None:
    store = _repository()
    first = store.publish("agg.weigh", "agg", 1, {"active": True})
    store.publish("agg.persist", "agg", 1, {"active": True})
    tombstones = store.rollback_after(first.seq, reason="operator", origin="console", generation=0)
    assert len(tombstones) == 1
    assert [record.kind for record in store.visible()] == ["agg.weigh"]


def test_tombstone_needs_a_committed_target() -> None:
    store = _repository()
    with pytest.raises(UnknownRecordError):
        store.tombstone(4, reason="operator", origin="console", generation=0)


def test_snapshot_restores_the_tail(it_data_dir=None) -> None:
    store = _repository()
    store.publish("agg.weigh", "agg", 1, {"active": True, "actual_kg": 4800})
    snapshot = store.snapshot(generation=1, validity=Validity.of(0, 32))
    store.publish("agg.persist", "agg", 1, {"active": True})
    report = store.restore(now=1)
    assert report.used_snapshot_id == snapshot.snapshot_id
    assert report.replayed_records == 1
    assert report.state["agg"]["weigh"]["actual_kg"] == 4800
    assert report.state["agg"]["persist"]["active"] is True


def test_require_durable_rejects_a_staged_record() -> None:
    store = _repository()
    record = store.stage("agg.weigh", "agg", 1, {"active": True})
    from mixplant.errors import NotDurableError

    with pytest.raises(NotDurableError):
        store.require_durable(record.seq, action="agg.drop")


def test_memory_backend_separates_staged_from_durable() -> None:
    backend = MemoryBackend()
    backend.append(JournalEntry(entry_type="durable", tick=1, seq=0))
    assert backend.staged() == 1
    assert backend.read() == []
    backend.flush_now()
    assert backend.staged() == 0
    assert len(backend.read()) == 1
    backend.close()
