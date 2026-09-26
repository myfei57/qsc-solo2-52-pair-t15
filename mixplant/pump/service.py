"""Delivery service: prime, start, stroke and pressure."""

from __future__ import annotations

from typing import Any

from ..errors import OrderViolationError
from ..service_base import PlantService
from ..statemachine.phases import DeliveryPhase
from .pressure import pressure_reading
from .pump import PRESSURE_KIND, RUN_KIND, START_KIND, STROKE_KIND
from .runloop import RunLoop
from .start import require_primed, start_payload


class PumpService(PlantService):
    """Starts the delivery pump only after the prime was confirmed."""

    origin = "pump"
    line = "delivery"
    subject = "pump"

    def __init__(self, context, machine=None, stroke_l: float = 320.0) -> None:
        super().__init__(context, machine)
        self.run = RunLoop()
        self.stroke_l = stroke_l

    def start(self) -> dict[str, Any]:
        """Start the delivery pump."""

        self.require("pump.start")
        prime = self.payload_entry("water", "prime")
        primed_l = float(prime.get("litres", 0.0)) if prime else 0.0
        require_primed(primed_l=primed_l, minimum_l=self.context.config.limits.prime_water_min_l)
        self.run.start()
        payload = start_payload(primed_l=primed_l, stroke_l=self.stroke_l)
        self.publish(RUN_KIND, payload)
        self.publish(START_KIND, payload)
        if self.machine.is_at(DeliveryPhase.PRIMED.value):
            self.advance(DeliveryPhase.PUMPING.value, "prime confirmed before the pump started")
        self.emit("pump.started", payload)
        return {"start": payload, "run": self.run.describe()}

    def prime_confirmed(self) -> dict[str, Any]:
        """Move the delivery line to its primed stage."""

        if self.machine.is_at(DeliveryPhase.DELIVERED.value):
            self.rewind(DeliveryPhase.IDLE.value, "delivery line reset for the next truck")
        if self.machine.is_at(DeliveryPhase.IDLE.value):
            self.advance(DeliveryPhase.PRIMED.value, "prime water confirmed")
        return {"phase": self.machine.phase, "sequence": self.machine.order()}

    def stroke(self, *, volume_m3: float) -> dict[str, Any]:
        """Record one stroke of the running pump."""

        self.require("pump.stroke")
        record = self.run.add(volume_m3)
        self.publish(STROKE_KIND, record.describe())
        self.emit("pump.stroke", record.describe())
        return {"stroke": record.describe(), "run": self.run.describe()}

    def observe_pressure(self, *, reading_mpa: float) -> dict[str, Any]:
        """Record a delivery pressure reading."""

        reading = pressure_reading(thresholds=self.context.thresholds, reading_mpa=reading_mpa)
        self.publish(PRESSURE_KIND, reading.describe())
        if not reading.ok:
            self.raise_alarm("pump.pressure_over_limit", reading.describe())
        self.emit("pump.pressure", reading.describe())
        return {"pressure": reading.describe(), "run": self.run.describe()}

    def finish(self) -> dict[str, Any]:
        """Finish the pumping run once the delivery target is reached."""

        if not self.run.running:
            raise OrderViolationError("the pump is not running")
        report = self.run.describe()
        self.run.stop()
        if self.machine.is_at(DeliveryPhase.PUMPING.value):
            self.advance(DeliveryPhase.DELIVERED.value, "delivery volume reached")
        self.emit("pump.finished", report)
        return {"report": report, "phase": self.machine.phase}

    def status(self) -> dict[str, Any]:
        run = self.payload_entry("pump", "run")
        pressure = self.payload_entry("pump", "pressure")
        return {
            "phase": self.machine.phase,
            "sequence": self.machine.order(),
            "running": bool(run.get("active", False)) if run else False,
            "strokes": len(self.run.strokes()),
            "volume_m3": self.run.volume_m3,
            "pressure": None if pressure is None else dict(pressure),
        }
