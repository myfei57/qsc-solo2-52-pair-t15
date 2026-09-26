"""The unit layout the station boots with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..errors import ValidationError
from .registry import DeviceKind, DeviceRegistry


@dataclass(frozen=True, slots=True)
class Topology:
    """A named station layout: which bins feed which material."""

    name: str
    bins: Mapping[str, str]
    silos: Mapping[str, str]
    water: str = "water-tank"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("topology must be named")
        if not self.bins:
            raise ValidationError("topology needs at least one bin")

    def source_for(self, material: str) -> str:
        """Return the unit that feeds ``material`` to the mixer."""

        for bin_name, loaded in self.bins.items():
            if loaded == material:
                return bin_name
        for silo_name, loaded in self.silos.items():
            if loaded == material:
                return silo_name
        if material == "water":
            return self.water
        raise ValidationError("no unit feeds this material", material=material, topology=self.name)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "bins": dict(self.bins), "silos": dict(self.silos), "water": self.water}


def default_topology() -> Topology:
    """Return the layout the station ships with."""

    return Topology(
        name="plant-a",
        bins={"bin-1": "sand", "bin-2": "gravel", "bin-3": "gravel", "bin-4": "admixture"},
        silos={"silo-1": "cement", "silo-2": "fly-ash"},
        water="tank-1",
    )


def build_registry(topology: Topology, extras: Iterable[tuple[str, DeviceKind, str]] = ()) -> DeviceRegistry:
    """Populate a registry from ``topology`` plus the fixed units."""

    registry = DeviceRegistry()
    for bin_name, material in topology.bins.items():
        registry.register(bin_name, DeviceKind.BIN, material)
    for silo_name, material in topology.silos.items():
        registry.register(silo_name, DeviceKind.SILO, material)
    for name, kind, role in extras:
        registry.register(name, kind, role)
    return registry


def device_names(registry: DeviceRegistry, kind: DeviceKind) -> tuple[str, ...]:
    """Return the names of every unit of ``kind``."""

    return tuple(device.name for device in registry.of_kind(kind))
