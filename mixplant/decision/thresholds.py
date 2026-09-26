"""Named bounds that readings are checked against."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..config import Limits
from ..errors import BelowLimitError, OverLimitError, ValidationError

MAX = "max"
MIN = "min"
DIRECTIONS = (MAX, MIN)


@dataclass(frozen=True, slots=True)
class Verdict:
    """The outcome of checking one reading against one bound."""

    name: str
    reading: float
    limit: float
    direction: str
    ok: bool
    code: str

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reading": self.reading,
            "limit": self.limit,
            "direction": self.direction,
            "ok": self.ok,
            "code": self.code,
        }


@dataclass(frozen=True, slots=True)
class Threshold:
    """One named bound together with the direction it refuses from."""

    name: str
    limit: float
    direction: str = MAX
    unit: str = ""

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValidationError("threshold direction must be max or min", direction=self.direction)

    def evaluate(self, reading: float) -> Verdict:
        """Return the verdict for ``reading`` without raising."""

        if self.direction == MAX:
            ok = reading <= self.limit
            code = "ok" if ok else "over_limit"
        else:
            ok = reading >= self.limit
            code = "ok" if ok else "below_limit"
        return Verdict(
            name=self.name,
            reading=reading,
            limit=self.limit,
            direction=self.direction,
            ok=ok,
            code=code,
        )

    def require(self, reading: float) -> Verdict:
        """Return the verdict or raise the limit error it maps to."""

        verdict = self.evaluate(reading)
        if verdict.ok:
            return verdict
        if self.direction == MAX:
            raise OverLimitError(
                "reading crossed an upper bound",
                name=self.name,
                reading=reading,
                limit=self.limit,
                unit=self.unit,
            )
        raise BelowLimitError(
            "reading dropped under a lower bound",
            name=self.name,
            reading=reading,
            limit=self.limit,
            unit=self.unit,
        )

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "limit": self.limit, "direction": self.direction, "unit": self.unit}


class ThresholdSet:
    """Every bound the decision layer evaluates, addressed by name."""

    __slots__ = ("_entries",)

    def __init__(self, entries: Mapping[str, Threshold]) -> None:
        self._entries = dict(entries)

    @classmethod
    def from_limits(cls, limits: Limits) -> "ThresholdSet":
        """Build the standard bound set from the configured limits."""

        entries = {
            "moisture": Threshold("moisture", limits.moisture_max_percent, MAX, "%"),
            "scale_deviation": Threshold("scale_deviation", limits.scale_tolerance_percent, MAX, "%"),
            "cement_flow": Threshold("cement_flow", limits.cement_flow_max_kgs, MAX, "kg/s"),
            "water_flow": Threshold("water_flow", limits.water_flow_max_lps, MAX, "L/s"),
            "hopper_residual": Threshold("hopper_residual", limits.hopper_residual_max_kg, MAX, "kg"),
            "pump_pressure": Threshold("pump_pressure", limits.pump_pressure_max_mpa, MAX, "MPa"),
            "prime_water": Threshold("prime_water", limits.prime_water_min_l, MIN, "L"),
        }
        return cls(entries)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def get(self, name: str) -> Threshold:
        """Return the bound called ``name`` or refuse the lookup."""

        entry = self._entries.get(name)
        if entry is None:
            raise ValidationError("unknown threshold", name=name, known=list(self.names()))
        return entry

    def evaluate(self, name: str, reading: float) -> Verdict:
        return self.get(name).evaluate(reading)

    def require(self, name: str, reading: float) -> Verdict:
        return self.get(name).require(reading)

    def describe(self) -> dict[str, Any]:
        return {name: self._entries[name].describe() for name in self.names()}
