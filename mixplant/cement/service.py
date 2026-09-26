"""Cement service: the gate, the flow and the silo inventory."""

from __future__ import annotations

from typing import Any

from ..service_base import PlantService
from ..statemachine.phases import MixPhase
from .flow import flow_reading
from .gate import gate_state
from .inventory import InventoryLedger
from .silo import silo_state

GATE_KIND = "cement.gate"
FLOW_KIND = "cement.flow"
SILO_KIND = "cement.silo"


class CementService(PlantService):
    """Feeds dry binder through a gate that the mixing line must open first."""

    origin = "cement"
    line = "mix"
    subject = "cement"

    def __init__(self, context, machine=None, opening: dict[str, float] | None = None) -> None:
        super().__init__(context, machine)
        self.ledger = InventoryLedger(opening or {"silo-1": 60000.0, "silo-2": 25000.0})

    def load_silo(self, *, silo: str, material: str, level_kg: float) -> dict[str, Any]:
        """Record the level and contents of a silo."""

        state = silo_state(silo, material, level_kg)
        self.ledger.deliver(silo, level_kg)
        self.publish(SILO_KIND, {"active": True, "silo": state.name, "material": state.material, "level_kg": level_kg})
        return {"silo": {"name": state.name, "material": state.material, "level_kg": state.level_kg}}

    def open_gate(self, *, silo: str, target_kg: float) -> dict[str, Any]:
        """Open the cement gate towards the mixer."""

        self.require_order(target_kg > 0, "the cement gate needs a positive target", silo=silo)
        state = gate_state(open=True, silo=silo, target_kg=target_kg)
        self.publish(GATE_KIND, state.describe())
        self.emit("cement.gate_opened", {"silo": silo, "target_kg": state.target_kg})
        return {"gate": state.describe(), "inventory": self.ledger.levels().describe()}

    def close_gate(self, *, silo: str, mass_kg: float, rate_kgs: float) -> dict[str, Any]:
        """Close the gate after a measured discharge."""

        self.require("cement.feed")
        state = gate_state(open=False, silo=silo, target_kg=mass_kg)
        reading = flow_reading(
            thresholds=self.context.thresholds,
            silo=silo,
            rate_kgs=rate_kgs,
            mass_kg=mass_kg,
        )
        level = self.ledger.draw(silo, mass_kg)
        self.publish(FLOW_KIND, reading.describe())
        self.publish(GATE_KIND, state.describe())
        self.publish(SILO_KIND, {"active": True, "silo": silo, "material": "cement", "level_kg": level})
        if not reading.ok:
            self.raise_alarm("cement.flow_over_limit", reading.describe())
        self.emit("cement.fed", {"silo": silo, "mass_kg": reading.mass_kg})
        if self.machine.is_at(MixPhase.WATER_IN.value):
            self.advance(MixPhase.CEMENT_IN.value, "binder washed in after the water")
        return {"flow": reading.describe(), "level_kg": level, "inventory": self.ledger.levels().describe()}

    def inventory(self) -> dict[str, Any]:
        levels = self.ledger.levels()
        return {"levels": {name: levels.level(name) for name in levels.levels}}

    def status(self) -> dict[str, Any]:
        gate = self.payload_entry("cement", "gate")
        flow = self.payload_entry("cement", "flow")
        silo = self.payload_entry("cement", "silo")
        return {
            "gate_open": bool(gate.get("active", False)) if gate else False,
            "silo": gate.get("silo") if gate else None,
            "target_kg": gate.get("target_kg") if gate else None,
            "flow": None if flow is None else dict(flow),
            "level_kg": None if silo is None else silo.get("level_kg"),
            "inventory": self.ledger.levels().describe()["levels"],
        }
