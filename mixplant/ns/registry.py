"""The device registry that gives every unit a stable name."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..errors import DuplicateError, NotFoundError, ValidationError


class DeviceKind(str, Enum):
    """The unit families the station wires together."""

    BIN = "bin"
    SILO = "silo"
    SCALE = "scale"
    MIXER = "mixer"
    HOPPER = "hopper"
    PUMP = "pump"
    SAMPLER = "sampler"
    TANK = "tank"


@dataclass(frozen=True, slots=True)
class Device:
    """One addressable unit of the station."""

    name: str
    kind: DeviceKind
    role: str

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "kind": str(self.kind.value), "role": self.role}


class DeviceRegistry:
    """Names every unit so a command can address it without guessing."""

    __slots__ = ("_devices",)

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}

    def register(self, name: str, kind: DeviceKind, role: str) -> Device:
        """Add a unit and refuse a reused name."""

        if not name:
            raise ValidationError("device name must not be empty")
        if name in self._devices:
            raise DuplicateError("device name was reused", name=name)
        device = Device(name=name, kind=kind, role=role)
        self._devices[name] = device
        return device

    def require(self, name: str) -> Device:
        device = self._devices.get(name)
        if device is None:
            raise NotFoundError("device is not part of the station", name=name)
        return device

    def of_kind(self, kind: DeviceKind) -> tuple[Device, ...]:
        return tuple(device for device in self._devices.values() if device.kind == kind)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._devices))

    def describe(self) -> list[dict[str, Any]]:
        return [self._devices[name].describe() for name in self.names()]
