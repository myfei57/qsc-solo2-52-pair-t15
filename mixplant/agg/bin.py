"""The bin a material is loaded from, valid for one recipe version."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class BinState:
    """One bin and the material it currently holds."""

    bin_name: str
    material: str
    version: int

    def __post_init__(self) -> None:
        if not self.bin_name:
            raise ValidationError("bin name must not be empty")
        if not self.material:
            raise ValidationError("bin material must not be empty", bin=self.bin_name)
        if self.version < 0:
            raise ValidationError("bin mapping version must not be negative", bin=self.bin_name)

    def describe(self) -> dict[str, Any]:
        return {"active": True, "bin": self.bin_name, "material": self.material, "version": self.version}


def refresh(bin_name: str, material: str, version: int) -> BinState:
    """Refresh a bin assignment after a silo or bunker change."""

    return BinState(bin_name=bin_name, material=material, version=version)
