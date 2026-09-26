"""Watermark value object for the record stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Watermark:
    """How far the stream has been written and how far it is readable."""

    committed_seq: int = 0
    durable_seq: int = 0
    tick: int = 0
    snapshot_seq: int = 0

    def describe(self) -> dict[str, Any]:
        return {
            "committed_seq": self.committed_seq,
            "durable_seq": self.durable_seq,
            "snapshot_seq": self.snapshot_seq,
            "tick": self.tick,
        }


def advance_watermark(current: int, candidate: int) -> int:
    """Keep a monotonic helper value used for the snapshot watermark."""

    return candidate if candidate > current else current
