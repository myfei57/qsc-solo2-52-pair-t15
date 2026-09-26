"""Facade that ties the journal, watermark, tombstones and snapshots together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..clock import Clock
from ..errors import NotDurableError, RecordError, RestoreError, UnknownRecordError
from ..ids import SequenceIds
from ..versioning.expiry import Validity
from .codec import ENTRY_APPEND, ENTRY_COMMIT, ENTRY_DURABLE, JournalEntry
from .journal import FileBackend, LogBackend, MemoryBackend
from .records import TOMBSTONE_KIND, Record
from .replay import merge_state, reduce_state
from .snapshot import Snapshot, SnapshotStore
from .tombstone import effective_records, rollback_targets
from .watermark import Watermark, advance_watermark


@dataclass(frozen=True, slots=True)
class RestoreReport:
    """What a restart decided to do."""

    used_snapshot_id: str | None
    replayed_records: int
    rejected_snapshots: tuple[Mapping[str, Any], ...]
    watermark: Watermark
    state: Mapping[str, Any]

    def describe(self) -> dict[str, Any]:
        return {
            "used_snapshot_id": self.used_snapshot_id,
            "replayed_records": self.replayed_records,
            "rejected_snapshots": [dict(item) for item in self.rejected_snapshots],
            "watermark": self.watermark.describe(),
        }


class RecordRepository:
    """Read and write side of the streaming store."""

    def __init__(
        self,
        backend: LogBackend,
        snapshots: SnapshotStore,
        clock: Clock,
        ids: SequenceIds,
    ) -> None:
        self._backend = backend
        self._snapshots = snapshots
        self._clock = clock
        self._ids = ids
        self._records: list[Record] = []
        self._durable_seq = 0
        self._committed_seq = 0
        self._snapshot_seq = 0
        self._load_backend()

    @classmethod
    def open(cls, data_dir: Path | str, clock: Clock, ids: SequenceIds) -> "RecordRepository":
        """Open the store that lives below ``data_dir``."""

        root = Path(data_dir)
        backend = FileBackend(root / "journal.jsonl")
        snapshots = SnapshotStore(root / "snapshots")
        return cls(backend, snapshots, clock, ids)

    @classmethod
    def in_memory(cls, clock: Clock, ids: SequenceIds) -> "RecordRepository":
        """Open a store that never touches the disk."""

        return cls(MemoryBackend(), SnapshotStore(None), clock, ids)

    @property
    def snapshots(self) -> SnapshotStore:
        return self._snapshots

    def _load_backend(self) -> None:
        for entry in self._backend.read():
            if entry.entry_type == ENTRY_APPEND and entry.record is not None:
                self._records.append(entry.record)
            elif entry.entry_type == ENTRY_DURABLE and entry.seq is not None:
                self._durable_seq = max(self._durable_seq, entry.seq)
            elif entry.entry_type == ENTRY_COMMIT and entry.seq is not None:
                self._committed_seq = max(self._committed_seq, entry.seq)
        for index, record in enumerate(self._records, start=1):
            if record.seq != index:
                raise RestoreError(
                    "the journal is missing a record in the middle of the stream",
                    expected_seq=index,
                    found_seq=record.seq,
                )

    def _append_entry(self, entry: JournalEntry) -> None:
        self._backend.append(entry)

    def watermark(self) -> Watermark:
        return Watermark(
            committed_seq=self._committed_seq,
            durable_seq=self._durable_seq,
            tick=self._clock.now(),
            snapshot_seq=self._snapshot_seq,
        )

    def last_seq(self) -> int:
        return len(self._records)

    def staged_records(self) -> tuple[Record, ...]:
        """Return records written but not flushed yet."""

        return tuple(rec for rec in self._records if rec.seq > self._durable_seq)

    def stage(self, kind: str, origin: str, generation: int, payload: Mapping[str, Any]) -> Record:
        """Append a record without making it durable or visible."""

        record = Record.create(
            seq=len(self._records) + 1,
            kind=kind,
            origin=origin,
            generation=generation,
            tick=self._clock.now(),
            payload=payload,
        )
        self._records.append(record)
        self._append_entry(JournalEntry(entry_type=ENTRY_APPEND, tick=record.tick, record=record))
        return record

    def flush(self) -> Watermark:
        """Make every staged record durable."""

        if self._durable_seq < len(self._records):
            self._append_entry(
                JournalEntry(entry_type=ENTRY_DURABLE, tick=self._clock.now(), seq=len(self._records))
            )
        self._backend.flush_now()
        self._durable_seq = len(self._records)
        return self.watermark()

    def commit(self) -> Watermark:
        """Commit everything that is currently durable."""

        return self.commit_through(self._durable_seq)

    def commit_through(self, seq: int) -> Watermark:
        """Move the commit watermark up to ``seq``."""

        if seq < self._committed_seq:
            raise RecordError(
                "the commit watermark never moves backwards",
                requested=seq,
                committed=self._committed_seq,
            )
        if seq > self._durable_seq:
            raise RecordError(
                "cannot commit beyond the durable watermark",
                requested=seq,
                durable=self._durable_seq,
            )
        self._committed_seq = seq
        self._append_entry(JournalEntry(entry_type=ENTRY_COMMIT, tick=self._clock.now(), seq=seq))
        self._backend.flush_now()
        return self.watermark()

    def publish(self, kind: str, origin: str, generation: int, payload: Mapping[str, Any]) -> Record:
        """Stage, flush and commit one record."""

        record = self.stage(kind, origin, generation, payload)
        self.flush()
        self.commit_through(record.seq)
        return record

    def require_durable(self, seq: int, *, action: str) -> Record:
        """Return a record only when it has reached the durable watermark."""

        for record in self._records:
            if record.seq == seq:
                if record.seq > self._durable_seq:
                    raise NotDurableError("record was staged but never flushed", action=action, seq=seq)
                return record
        raise UnknownRecordError("record does not exist", action=action, seq=seq)

    def visible(self) -> tuple[Record, ...]:
        """Return the committed, non tombstoned records."""

        return effective_records(self._records[: self._committed_seq])

    def committed_records(self) -> tuple[Record, ...]:
        """Return every committed record, tombstones included."""

        return tuple(self._records[: self._committed_seq])

    def state(self) -> dict[str, Any]:
        return reduce_state(self.visible())

    def history(self, kind: str) -> tuple[Record, ...]:
        """Return every surviving record of ``kind`` in write order."""

        return tuple(rec for rec in self.visible() if rec.kind == kind)

    def latest(self, kind: str) -> Record | None:
        """Return the newest surviving record of ``kind``."""

        found = None
        for record in self.visible():
            if record.kind == kind:
                found = record
        return found

    def tombstone(self, target_seq: int, *, reason: str, origin: str, generation: int) -> Record:
        """Neutralise one earlier record."""

        if target_seq < 1 or target_seq > len(self._records):
            raise UnknownRecordError("tombstone target does not exist", target=target_seq)
        if target_seq > self._committed_seq:
            raise RecordError("cannot tombstone a record that was never committed", target=target_seq)
        record = self._append_tombstone(target_seq, reason, origin, generation)
        self.flush()
        self.commit_through(record.seq)
        return record

    def _append_tombstone(self, target_seq: int, reason: str, origin: str, generation: int) -> Record:
        record = Record.create(
            seq=len(self._records) + 1,
            kind=TOMBSTONE_KIND,
            origin=origin,
            generation=generation,
            tick=self._clock.now(),
            payload={"reason": reason, "target_seq": target_seq},
            tombstone_of=target_seq,
        )
        self._records.append(record)
        self._append_entry(JournalEntry(entry_type=ENTRY_APPEND, tick=record.tick, record=record))
        return record

    def rollback_after(
        self,
        seq: int,
        *,
        reason: str,
        origin: str,
        generation: int,
    ) -> tuple[Record, ...]:
        """Tombstone every committed record after ``seq`` in one commit."""

        targets = rollback_targets(self._records[: self._committed_seq], seq)
        if not targets:
            return ()
        records = tuple(self._append_tombstone(target, reason, origin, generation) for target in targets)
        self.flush()
        self.commit_through(records[-1].seq)
        return records

    def snapshot(self, *, generation: int, validity: Validity, scope: str = "snap") -> Snapshot:
        """Materialise the committed state and store it."""

        snapshot = Snapshot(
            snapshot_id=self._ids.next(scope),
            watermark_seq=self._committed_seq,
            generation=generation,
            tick=self._clock.now(),
            state=reduce_state(self.visible()),
            validity=validity,
        )
        self._snapshots.save(snapshot)
        self._snapshot_seq = advance_watermark(self._snapshot_seq, snapshot.watermark_seq)
        return snapshot

    def restore(self, now: int) -> RestoreReport:
        """Rebuild state from the newest usable snapshot plus the tail."""

        candidates = self._snapshots.load_all()
        rejected: list[Mapping[str, Any]] = []
        base: Mapping[str, Any] = {}
        from_seq = 0
        used: str | None = None
        if candidates:
            newest = candidates[-1]
            if newest.watermark_seq > self._committed_seq:
                for candidate in candidates:
                    rejected.append({**candidate.describe(now), "reject": "beyond_watermark"})
            elif newest.is_expired(now):
                rejected.append({**newest.describe(now), "reject": "expired"})
                for stale in candidates[:-1]:
                    rejected.append({**stale.describe(now), "reject": "superseded_by_expired_newer"})
            else:
                base = newest.state
                from_seq = newest.watermark_seq
                used = newest.snapshot_id
                for stale in candidates[:-1]:
                    rejected.append({**stale.describe(now), "reject": "superseded"})
        tail = tuple(rec for rec in self.visible() if rec.seq > from_seq)
        merged = merge_state(base, reduce_state(tail)) if base else reduce_state(tail)
        return RestoreReport(
            used_snapshot_id=used,
            replayed_records=len(tail),
            rejected_snapshots=tuple(rejected),
            watermark=self.watermark(),
            state=merged,
        )

    def close(self) -> None:
        self._backend.close()
