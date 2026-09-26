"""Concrete grades a recipe can be written against."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class Grade:
    """One deliverable grade together with its acceptance band."""

    code: str
    strength_mpa: float
    slump_mm: int

    def __post_init__(self) -> None:
        if not self.code:
            raise ValidationError("grade code must not be empty")
        if self.strength_mpa <= 0:
            raise ValidationError("grade strength must be positive", code=self.code)
        if self.slump_mm < 0:
            raise ValidationError("grade slump must not be negative", code=self.code)

    def describe(self) -> dict[str, Any]:
        return {"code": self.code, "strength_mpa": self.strength_mpa, "slump_mm": self.slump_mm}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Grade":
        return cls(
            code=str(document["code"]),
            strength_mpa=float(document["strength_mpa"]),
            slump_mm=int(document["slump_mm"]),
        )


CATALOGUE: Mapping[str, Grade] = {
    "C20": Grade(code="C20", strength_mpa=20.0, slump_mm=160),
    "C30": Grade(code="C30", strength_mpa=30.0, slump_mm=180),
    "C40": Grade(code="C40", strength_mpa=40.0, slump_mm=180),
}


def grade_for(code: str) -> Grade:
    """Return a catalogue grade or refuse the lookup."""

    grade = CATALOGUE.get(code)
    if grade is None:
        raise ValidationError("unknown grade", code=code, known=sorted(CATALOGUE))
    return grade


def catalogue() -> list[dict[str, Any]]:
    """Describe every grade the book accepts."""

    return [CATALOGUE[code].describe() for code in sorted(CATALOGUE)]
