"""Structural checks a recipe must pass before it can be published."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Limits
from .recipe import Recipe


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One reason a recipe was accepted or refused."""

    code: str
    ok: bool
    detail: str

    def describe(self) -> dict[str, Any]:
        return {"code": self.code, "ok": self.ok, "detail": self.detail}


def validate_recipe(recipe: Recipe, limits: Limits) -> list[ValidationFinding]:
    """Return every structural finding for ``recipe``."""

    findings = [
        ValidationFinding(
            code="materials",
            ok=bool(recipe.factors),
            detail=f"{len(recipe.factors)} material factors declared",
        ),
        ValidationFinding(
            code="mix_time",
            ok=recipe.mix_time_ticks >= 1,
            detail=f"mixing window is {recipe.mix_time_ticks} ticks",
        ),
        ValidationFinding(
            code="moisture_reference",
            ok=recipe.moisture_ref_percent <= limits.moisture_max_percent,
            detail=f"moisture reference {recipe.moisture_ref_percent}% against {limits.moisture_max_percent}%",
        ),
    ]
    return findings


def require_valid(findings: list[ValidationFinding]) -> None:
    """Raise when any finding failed."""

    from ..errors import ValidationError

    failed = [finding for finding in findings if not finding.ok]
    if failed:
        raise ValidationError(
            "recipe failed validation",
            findings=[finding.describe() for finding in failed],
        )
