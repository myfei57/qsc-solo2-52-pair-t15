"""What the station is made of, and which lines the runtime drives."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..ns.registry import DeviceKind, DeviceRegistry
from ..ns.topology import Topology, device_names
from ..statemachine.phases import phase_names
from .events import catalogue, events_for, origins

LINES: tuple[str, ...] = ("batch", "mix", "delivery")


def describe_manifest(
    *,
    station: str,
    topology: Topology,
    registry: DeviceRegistry,
    record_kinds: Sequence[str],
    machines: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe the units, the lines and the record kinds of the plant."""

    current = line_machines(machines)
    return {
        "station": station,
        "topology": topology.describe(),
        "devices": registry.describe(),
        "bins": list(device_names(registry, DeviceKind.BIN)),
        "silos": list(device_names(registry, DeviceKind.SILO)),
        "lines": {
            line: {"declared": phase_names(line), **current.get(line, {})} for line in LINES
        },
        "record_kinds": list(record_kinds),
        "events": catalogue(),
        "events_by_origin": {origin: list(events_for(origin)) for origin in origins()},
    }


def line_machines(machines: Mapping[str, Any]) -> dict[str, Any]:
    """Describe the stage machines the manifest knows about."""

    return {
        line: {"phase": machine.phase, "sequence": machine.order(), "next": machine.next_phase()}
        for line, machine in machines.items()
    }
