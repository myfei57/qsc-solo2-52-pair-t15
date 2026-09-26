"""Scale arithmetic: deviation, tolerance and the calibration correction."""

from __future__ import annotations

from ..errors import ValidationError


def require_positive(value: float, *, field: str) -> float:
    """Return ``value`` when it is positive."""

    if value <= 0:
        raise ValidationError("value must be positive", field=field, value=value)
    return value


def deviation_percent(actual: float, target: float) -> float:
    """Return how far off the scale is, as a percentage of the target."""

    require_positive(target, field="target")
    return round(abs(actual - target) / target * 100.0, 4)


def within_tolerance(deviation: float, tolerance_percent: float) -> bool:
    """Return whether ``deviation`` is inside the allowed band."""

    if tolerance_percent < 0:
        raise ValidationError("tolerance must not be negative", tolerance=tolerance_percent)
    return deviation <= tolerance_percent
