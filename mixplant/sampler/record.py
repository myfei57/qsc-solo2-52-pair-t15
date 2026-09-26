"""The laboratory record a sample is filed under."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class SampleRecord:
    """One filed laboratory sample."""

    sample_id: str
    batch_id: str
    grade: str
    litres: float

    def __post_init__(self) -> None:
        if not self.sample_id:
            raise ValidationError("a sample needs an identity")
        if not self.batch_id:
            raise ValidationError("a sample needs a batch identity", sample=self.sample_id)

    def describe(self) -> dict[str, Any]:
        return {
            "active": True,
            "sample_id": self.sample_id,
            "batch_id": self.batch_id,
            "grade": self.grade,
            "litres": self.litres,
        }


def sample_record(*, sample_id: str, batch_id: str, grade: str, litres: float) -> SampleRecord:
    """Build one sample record."""

    return SampleRecord(sample_id=sample_id, batch_id=batch_id, grade=grade, litres=round(litres, 4))
