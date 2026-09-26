"""Read model behind the mixing and cycle overview."""

from __future__ import annotations

from typing import Any


def mix_view(*, mix_service: Any, cement_service: Any, water_service: Any) -> dict[str, Any]:
    """Build the mixing view for the console."""

    return {
        "mixer": mix_service.status(),
        "inputs": list(mix_service.inputs()),
        "cement": cement_service.status(),
        "water": water_service.status(),
        "cycle": mix_service.cycles.current().describe() if mix_service.cycles.current() else None,
    }
