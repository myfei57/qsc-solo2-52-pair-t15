"""Shared fixtures for the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mixplant.runtime import PlantRuntime  # noqa: E402
from mixplant.config import StationConfig  # noqa: E402
from tests.support import run_full_cycle  # noqa: E402


@pytest.fixture()
def runtime() -> PlantRuntime:
    plant = PlantRuntime(StationConfig(web_dir=ROOT / "web"), storage="memory")
    plant.bootstrap()
    return plant


@pytest.fixture()
def cycled(runtime: PlantRuntime) -> PlantRuntime:
    run_full_cycle(runtime)
    return runtime
