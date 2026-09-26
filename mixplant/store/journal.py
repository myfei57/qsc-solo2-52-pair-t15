"""Backends that persist journal entries.

Both backends separate ``append`` from ``flush`` on purpose: a staged entry
stays invisible to a reader that opens the backend again, which is how the
runtime models "written but not durable".
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from ..errors import ValidationError
from .codec import JournalEntry, decode_entry, encode_entry


class LogBackend(Protocol):
    """Storage behind the append only log."""

    def append(self, entry: JournalEntry) -> None:
        """Stage one entry."""

    def flush_now(self) -> None:
        """Make every staged entry durable."""

    def read(self) -> list[JournalEntry]:
        """Return the durable entries in write order."""

    def close(self) -> None:
        """Release any handle held by the backend."""


class MemoryBackend:
    """A backend that keeps staged and durable entries in memory."""

    __slots__ = ("_staged", "_durable")

    def __init__(self) -> None:
        self._staged: list[JournalEntry] = []
        self._durable: list[JournalEntry] = []

    def append(self, entry: JournalEntry) -> None:
        self._staged.append(entry)

    def flush_now(self) -> None:
        if not self._staged:
            return
        self._durable.extend(self._staged)
        self._staged.clear()

    def read(self) -> list[JournalEntry]:
        return list(self._durable)

    def staged(self) -> int:
        """Return how many entries are staged but not durable."""

        return len(self._staged)

    def close(self) -> None:
        return None


class FileBackend:
    """A backend that writes one json line per entry."""

    __slots__ = ("_path", "_handle")

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: JournalEntry) -> None:
        self._handle.write(encode_entry(entry))
        self._handle.write("\n")

    def flush_now(self) -> None:
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def read(self) -> list[JournalEntry]:
        if not self._path.exists():
            return []
        entries: list[JournalEntry] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    entries.append(decode_entry(line))
                except ValidationError as exc:
                    raise ValidationError(
                        "journal file contains an unreadable line", path=str(self._path), line=number
                    ) from exc
        return entries

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()
