"""Calibration baselines such as recipe factor and scale calibration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .expiry import Validity


@dataclass(frozen=True, slots=True)
class Baseline:
    """One named calibration value bound to a generation."""

    name: str
    value: float
    unit: str
    generation: int
    validity: Validity

    def is_expired(self, now: int) -> bool:
        return self.validity.is_expired(now)

    def require_fresh(self, now: int) -> None:
        self.validity.require_fresh(now, subject=f"baseline:{self.name}")

    def describe(self, now: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "generation": self.generation,
            "validity": self.validity.describe(now),
        }
        return payload

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "generation": self.generation,
            "validity": self.validity.to_document(),
        }
