"""Stage machines, the pre gate and the latch."""

from __future__ import annotations

import pytest

from mixplant.errors import OrderViolationError, ValidationError
from mixplant.statemachine.gate import PreGate
from mixplant.statemachine.interlock import InterlockRule
from mixplant.statemachine.machine import SequenceMachine
from mixplant.statemachine.phases import LINE_SEQUENCES, phase_names, sequence_for
from mixplant.interlocks import build_engine


def test_declared_sequences() -> None:
    assert phase_names("batch")[0] == "idle"
    assert phase_names("batch")[-1] == "dropped"
    assert set(LINE_SEQUENCES) == {"batch", "mix", "delivery"}
    with pytest.raises(ValidationError):
        sequence_for("missing")


def test_machine_only_advances_in_order() -> None:
    machine = SequenceMachine("batch")
    step = machine.advance("recipe_selected", tick=1, reason="selected")
    assert step.step == 1
    with pytest.raises(OrderViolationError):
        machine.advance("dropped", tick=2, reason="skip")


def test_machine_refuses_to_advance_past_the_last_stage() -> None:
    machine = SequenceMachine("delivery")
    machine.advance("primed", tick=1, reason="primed")
    machine.advance("pumping", tick=2, reason="pumping")
    machine.advance("delivered", tick=3, reason="delivered")
    with pytest.raises(OrderViolationError):
        machine.advance("delivered", tick=4, reason="again")


def test_machine_rewinds_backwards_only() -> None:
    machine = SequenceMachine("mix")
    machine.advance("water_in", tick=1, reason="water")
    step = machine.rewind_to("idle", tick=2, reason="reset")
    assert step.phase == "idle"
    with pytest.raises(OrderViolationError):
        machine.rewind_to("mixed", tick=3, reason="forward")


def test_machine_hydration_rebuilds_a_stage() -> None:
    machine = SequenceMachine("mix")
    machine.hydrate("mixing", step=3, tick=9)
    assert machine.phase == "mixing"
    assert machine.history()[-1].reason == "hydrated"


def test_gate_combines_stage_and_interlock() -> None:
    engine = build_engine((InterlockRule(name="open", action="test.action", requires=("flag",)),))
    gate = PreGate(engine)
    machine = SequenceMachine("batch")
    blocked = gate.evaluate("test.action", facts={"flag": True}, machine=machine, required_phase="weighed")
    assert blocked.allowed is False
    assert blocked.decision.blocking[0].startswith("stage:")
    with pytest.raises(OrderViolationError):
        gate.require("test.action", facts={"flag": True}, machine=machine, required_phase="weighed")
