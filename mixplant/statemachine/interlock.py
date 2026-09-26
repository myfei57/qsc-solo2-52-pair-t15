"""Preconditions that are evaluated against derived facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from ..errors import InterlockBlockedError, NotDurableError, ValidationError

DURABILITY_MARKER = "persisted"


@dataclass(frozen=True, slots=True)
class InterlockRule:
    """One precondition bound to an action."""

    name: str
    action: str
    requires: tuple[str, ...] = ()
    forbids: tuple[str, ...] = ()
    message: str = ""

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "action": self.action,
            "requires": list(self.requires),
            "forbids": list(self.forbids),
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class InterlockDecision:
    """Outcome of evaluating every rule bound to an action."""

    action: str
    allowed: bool
    blocking: tuple[str, ...]
    missing: tuple[str, ...] = ()
    message: str = ""
    checks: tuple[Mapping[str, object], ...] = field(default_factory=tuple)

    def describe(self) -> dict[str, object]:
        return {
            "action": self.action,
            "allowed": self.allowed,
            "blocking": list(self.blocking),
            "missing": list(self.missing),
            "message": self.message,
        }


class InterlockEngine:
    """Evaluates a rule table against a fact map."""

    __slots__ = ("_rules",)

    def __init__(self, rules: Sequence[InterlockRule]) -> None:
        self._rules = tuple(rules)
        names = [rule.name for rule in self._rules]
        if len(names) != len(set(names)):
            raise ValidationError("interlock rule names must be unique", names=names)

    def rules(self) -> tuple[InterlockRule, ...]:
        return self._rules

    def rules_for(self, action: str) -> tuple[InterlockRule, ...]:
        return tuple(rule for rule in self._rules if rule.action == action)

    def actions(self) -> tuple[str, ...]:
        """Return every action the rule table names, in first-seen order."""

        seen: list[str] = []
        for rule in self._rules:
            if rule.action not in seen:
                seen.append(rule.action)
        return tuple(seen)

    def evaluate(self, action: str, facts: Mapping[str, bool]) -> InterlockDecision:
        """Check every rule bound to ``action`` without raising."""

        blocking: list[str] = []
        missing: list[str] = []
        messages: list[str] = []
        checks: list[Mapping[str, object]] = []
        for rule in self.rules_for(action):
            satisfied = True
            rule_missing: list[str] = []
            for fact in rule.requires:
                if not facts.get(fact, False):
                    satisfied = False
                    rule_missing.append(fact)
            for fact in rule.forbids:
                if facts.get(fact, False):
                    satisfied = False
                    rule_missing.append(fact)
            checks.append(
                {
                    "rule": rule.name,
                    "satisfied": satisfied,
                    "unsatisfied": list(rule_missing),
                    "message": rule.message,
                }
            )
            if not satisfied:
                blocking.append(rule.name)
                for fact in rule_missing:
                    missing.append(fact)
                if rule.message:
                    messages.append(rule.message)
        return InterlockDecision(
            action=action,
            allowed=not blocking,
            blocking=tuple(blocking),
            missing=tuple(dict.fromkeys(missing)),
            message="; ".join(messages),
            checks=tuple(checks),
        )

    def require(self, action: str, facts: Mapping[str, bool]) -> InterlockDecision:
        """Raise unless every rule bound to ``action`` is satisfied."""

        decision = self.evaluate(action, facts)
        if decision.allowed:
            return decision
        unsatisfied: Iterable[str] = decision.missing
        if any(DURABILITY_MARKER in fact for fact in unsatisfied):
            raise NotDurableError(
                "prerequisite state was never written durably",
                action=action,
                blocking=list(decision.blocking),
                missing=list(decision.missing),
            )
        raise InterlockBlockedError(
            decision.message or "interlock is not satisfied",
            action=action,
            blocking=list(decision.blocking),
            missing=list(decision.missing),
        )
