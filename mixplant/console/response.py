"""Serialisation helpers for the console."""

from __future__ import annotations

import json
from typing import Any, Mapping

SNAPSHOT_PLACEHOLDER = "<!--STATE-->"


def encode_json(payload: Any) -> str:
    """Encode a payload deterministically."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2, default=str)


def inject_snapshot(page: str, snapshot: Mapping[str, Any]) -> str:
    """Replace the placeholder in ``page`` with the live snapshot."""

    if SNAPSHOT_PLACEHOLDER in page:
        return page.replace(SNAPSHOT_PLACEHOLDER, encode_json(snapshot))
    return f"{page}\n<script>window.__plantState__ = {encode_json(snapshot)};</script>\n"
