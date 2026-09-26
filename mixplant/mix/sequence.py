"""The fixed order in which the mixer takes its inputs."""

from __future__ import annotations

from typing import Any, Iterable

from ..errors import OrderViolationError, ValidationError
from .mix import INPUT_ORDER


def order_index(component: str) -> int:
    """Return the position of ``component`` in the declared input order."""

    try:
        return INPUT_ORDER.index(component)
    except ValueError as exc:
        raise ValidationError(
            "component is not part of the input order",
            component=component,
            order=list(INPUT_ORDER),
        ) from exc


def require_turn(component: str, already_fed: Iterable[str]) -> None:
    """Refuse an input that would skip ahead of the declared order."""

    position = order_index(component)
    fed = {str(item) for item in already_fed}
    for earlier in INPUT_ORDER[:position]:
        if earlier not in fed:
            raise OrderViolationError(
                "input was requested before an earlier one was fed",
                component=component,
                missing=earlier,
                order=list(INPUT_ORDER),
            )


def fed_sequence(already_fed: Iterable[str]) -> list[str]:
    """Return the inputs fed so far, in declared order."""

    fed = {str(item) for item in already_fed}
    return [component for component in INPUT_ORDER if component in fed]


def describe_order() -> dict[str, Any]:
    """Describe the declared input order for the console."""

    return {"order": list(INPUT_ORDER), "water_first": INPUT_ORDER[0] == "water"}
