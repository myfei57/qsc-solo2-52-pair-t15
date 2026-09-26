"""The interlock engine maps refusal kinds onto error types."""

from __future__ import annotations

import pytest

from mixplant.errors import InterlockBlockedError, NotDurableError, ValidationError
from mixplant.facts import derive_facts
from mixplant.interlocks import DEFAULT_RULES, build_engine
from mixplant.statemachine.interlock import InterlockRule


def test_every_rule_is_uniquely_named() -> None:
    names = [rule.name for rule in DEFAULT_RULES]
    assert len(names) == len(set(names))


def test_engine_lists_actions_in_first_seen_order() -> None:
    actions = build_engine().actions()
    assert actions[0] == "recipe.select"
    assert "agg.drop" in actions


def test_engine_allows_when_no_rules_match() -> None:
    decision = build_engine().evaluate("nothing.here", {})
    assert decision.allowed is True
    assert decision.blocking == ()


def test_engine_refuses_and_reports_the_missing_fact() -> None:
    decision = build_engine().evaluate("agg.drop", {})
    assert decision.allowed is False
    assert decision.missing == ("agg.weight_persisted",)


def test_engine_maps_a_durability_fact_to_not_durable() -> None:
    with pytest.raises(NotDurableError):
        build_engine().require("agg.drop", {})


def test_engine_maps_other_facts_to_interlock_blocked() -> None:
    with pytest.raises(InterlockBlockedError):
        build_engine().require("chute.open", {})


def test_duplicate_rule_names_are_refused() -> None:
    rule = InterlockRule(name="dup", action="agg.drop")
    with pytest.raises(ValidationError):
        build_engine((rule, rule))


def test_facts_follow_the_derived_state() -> None:
    state = {
        "agg": {"persist": {"active": True}},
        "mix": {"timer": {"finished": True}},
        "sampler": {"latch": {"active": True}},
    }
    facts = derive_facts(state)
    assert facts["agg.weight_persisted"] is True
    assert facts["mix.timed"] is True
    assert facts["sampler.latched"] is True
    assert facts["agg.dropped"] is False
