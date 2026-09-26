"""Water service: batching water and the pump prime."""

from __future__ import annotations

from typing import Any

from ..service_base import PlantService
from ..statemachine.phases import MixPhase
from .dispense import dispense_reading
from .prime import prime_reading
from .tank import tank_state
from .valve import valve_state

VALVE_KIND = "water.valve"
DISPENSE_KIND = "water.dispense"
PRIME_KIND = "water.prime"
TANK_KIND = "water.tank"


class WaterService(PlantService):
    """Meters batching water and confirms the pump prime."""

    origin = "water"
    line = "mix"
    subject = "water"

    def __init__(self, context, machine=None, tank_level_l: float = 20000.0) -> None:
        super().__init__(context, machine)
        self._level_l = tank_level_l

    def open_valve(self, *, target_l: float) -> dict[str, Any]:
        """Open the batching water valve."""

        self.require_order(target_l > 0, "the batching valve needs a positive target", target_l=target_l)
        state = valve_state(open=True, target_l=target_l)
        self.publish(VALVE_KIND, state.describe())
        self.publish(TANK_KIND, tank_state("tank-1", self._level_l).describe())
        self.emit("water.valve_opened", {"target_l": state.target_l})
        return {"valve": state.describe(), "tank_l": self._level_l}

    def dispense(self, *, litres: float, rate_lps: float) -> dict[str, Any]:
        """Meter batching water into the mixer; it must reach the mixer first."""

        self.require("water.dispense")
        reading = dispense_reading(thresholds=self.context.thresholds, litres=litres, rate_lps=rate_lps)
        self._level_l = round(self._level_l - litres, 4)
        self.publish(DISPENSE_KIND, reading.describe())
        self.publish(TANK_KIND, tank_state("tank-1", self._level_l).describe())
        self.publish(VALVE_KIND, valve_state(open=False, target_l=litres).describe())
        if not reading.ok:
            self.raise_alarm("water.flow_over_limit", reading.describe())
        self.emit("water.dispensed", {"litres": reading.litres})
        if self.machine.is_at(MixPhase.IDLE.value):
            self.advance(MixPhase.WATER_IN.value, "water reached the mixer before the binder")
        return {"dispense": reading.describe(), "tank_l": self._level_l}

    def prime(self, *, litres: float) -> dict[str, Any]:
        """Confirm the prime water the pump needs before it starts."""

        reading = prime_reading(thresholds=self.context.thresholds, litres=litres)
        if not reading.ok:
            self.raise_alarm("water.prime_insufficient", reading.describe())
        self.publish(PRIME_KIND, reading.describe())
        self.emit("water.primed", {"litres": reading.litres})
        return {"prime": reading.describe()}

    def tank(self) -> dict[str, Any]:
        return tank_state("tank-1", self._level_l).describe()

    def status(self) -> dict[str, Any]:
        valve = self.payload_entry("water", "valve")
        dispense = self.payload_entry("water", "dispense")
        prime = self.payload_entry("water", "prime")
        return {
            "valve_open": bool(valve.get("active", False)) if valve else False,
            "dispensed_l": float(dispense.get("litres", 0.0)) if dispense else 0.0,
            "dispensed_ok": None if dispense is None else bool(dispense.get("ok", False)),
            "primed_l": float(prime.get("litres", 0.0)) if prime else 0.0,
            "prime_ok": None if prime is None else bool(prime.get("ok", False)),
            "tank_l": self._level_l,
        }
