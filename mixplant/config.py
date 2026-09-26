"""Configuration values shared by the runtime and its services."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Limits:
    """Process bounds the decision layer evaluates readings against."""

    mix_time_ticks: int = 6
    moisture_max_percent: float = 9.0
    scale_tolerance_percent: float = 2.0
    cement_flow_max_kgs: float = 42.0
    water_flow_max_lps: float = 60.0
    hopper_residual_max_kg: float = 12.0
    pump_pressure_max_mpa: float = 8.0
    prime_water_min_l: float = 40.0
    sample_window_ticks: int = 8

    def as_mapping(self) -> dict[str, float]:
        return {
            "mix_time_ticks": float(self.mix_time_ticks),
            "moisture_max_percent": self.moisture_max_percent,
            "scale_tolerance_percent": self.scale_tolerance_percent,
            "cement_flow_max_kgs": self.cement_flow_max_kgs,
            "water_flow_max_lps": self.water_flow_max_lps,
            "hopper_residual_max_kg": self.hopper_residual_max_kg,
            "pump_pressure_max_mpa": self.pump_pressure_max_mpa,
            "prime_water_min_l": self.prime_water_min_l,
        }


@dataclass(frozen=True, slots=True)
class ValidityDefaults:
    """Default validity windows, expressed in ticks."""

    baseline_ttl_ticks: int = 32
    confirmation_ttl_ticks: int = 10
    snapshot_ttl_ticks: int = 64


@dataclass(frozen=True, slots=True)
class StationConfig:
    """Everything the runtime needs in order to boot."""

    station: str = "plant-a"
    host: str = "127.0.0.1"
    port: int = 8080
    data_dir: Path = Path("var/state")
    web_dir: Path = Path("web")
    limits: Limits = field(default_factory=Limits)
    defaults: ValidityDefaults = field(default_factory=ValidityDefaults)

    @classmethod
    def from_mapping(cls, document: Mapping[str, Any]) -> "StationConfig":
        """Build a config from a parsed json document."""

        limits = Limits(**dict(document.get("limits") or {}))
        defaults = ValidityDefaults(**dict(document.get("defaults") or {}))
        return cls(
            station=str(document.get("station", "plant-a")),
            host=str(document.get("host", "127.0.0.1")),
            port=int(document.get("port", 8080)),
            data_dir=Path(str(document.get("data_dir", "var/state"))),
            web_dir=Path(str(document.get("web_dir", "web"))),
            limits=limits,
            defaults=defaults,
        )

    @classmethod
    def load(cls, path: Path | str) -> "StationConfig":
        """Read a config file, falling back to the defaults when it is absent."""

        candidate = Path(path)
        if not candidate.exists():
            return cls()
        document = json.loads(candidate.read_text(encoding="utf-8"))
        return cls.from_mapping(document)

    def with_overrides(self, **changes: Any) -> "StationConfig":
        """Return a copy with ``changes`` applied."""

        return replace(self, **changes)

    def describe(self) -> Mapping[str, Any]:
        return {
            "station": self.station,
            "host": self.host,
            "port": self.port,
            "data_dir": str(self.data_dir),
            "limits": self.limits.as_mapping(),
        }
