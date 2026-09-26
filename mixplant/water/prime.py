"""The prime water a pump needs before it may start."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.thresholds import ThresholdSet
from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class PrimeReading:
    """How much priming water was confirmed for the delivery line."""

    litres: float
    ok: bool
    code: str

    def describe(self) -> dict[str, Any]:
        return {"active": True, "litres": self.litres, "ok": self.ok, "code": self.code}


def prime_reading(*, thresholds: ThresholdSet, litres: float) -> PrimeReading:
    """Check the priming volume against the configured floor."""

    if litres < 0:
        raise ValidationError("priming volume must not be negative", litres=litres)
    verdict = thresholds.evaluate("prime_water", litres)
    return PrimeReading(litres=round(litres, 4), ok=verdict.ok, code=verdict.code)
