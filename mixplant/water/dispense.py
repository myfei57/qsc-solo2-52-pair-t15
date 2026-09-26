"""Metered water delivered to the mixer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.thresholds import ThresholdSet
from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class DispenseReading:
    """One metering reading together with its verdict."""

    litres: float
    rate_lps: float
    ok: bool
    code: str

    def describe(self) -> dict[str, Any]:
        return {
            "active": True,
            "litres": self.litres,
            "rate_lps": self.rate_lps,
            "ok": self.ok,
            "code": self.code,
        }


def dispense_reading(*, thresholds: ThresholdSet, litres: float, rate_lps: float) -> DispenseReading:
    """Check one metering reading against the flow ceiling."""

    if litres <= 0:
        raise ValidationError("a dispense needs a positive volume", litres=litres)
    verdict = thresholds.evaluate("water_flow", rate_lps)
    return DispenseReading(litres=round(litres, 4), rate_lps=round(rate_lps, 4), ok=verdict.ok, code=verdict.code)
