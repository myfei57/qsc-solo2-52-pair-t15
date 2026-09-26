"""Named bounds refuse readings from the wrong side."""

from __future__ import annotations

import pytest

from mixplant.config import Limits
from mixplant.decision.thresholds import Threshold, ThresholdSet
from mixplant.errors import BelowLimitError, OverLimitError, ValidationError


def test_upper_bound() -> None:
    threshold = Threshold("moisture", 9.0)
    assert threshold.evaluate(8.0).ok is True
    assert threshold.evaluate(10.0).code == "over_limit"
    with pytest.raises(OverLimitError):
        threshold.require(10.0)


def test_lower_bound() -> None:
    threshold = Threshold("prime_water", 40.0, "min")
    assert threshold.evaluate(60.0).ok is True
    assert threshold.evaluate(10.0).code == "below_limit"
    with pytest.raises(BelowLimitError):
        threshold.require(10.0)


def test_direction_is_validated() -> None:
    with pytest.raises(ValidationError):
        Threshold("x", 1.0, "sideways")


def test_set_is_built_from_limits() -> None:
    thresholds = ThresholdSet.from_limits(Limits())
    assert "pump_pressure" in thresholds.names()
    assert thresholds.require("prime_water", 50.0).ok is True
    with pytest.raises(ValidationError):
        thresholds.get("missing")
