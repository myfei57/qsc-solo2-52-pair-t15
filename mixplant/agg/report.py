"""The weight report the audit log keeps for every batch."""

from __future__ import annotations

from typing import Any, Mapping

from .weigh import WeightReading


def weight_report(reading: WeightReading, *, batch_id: str, version: int) -> dict[str, Any]:
    """Build the audit report for one weighing."""

    return {
        "batch_id": batch_id,
        "version": version,
        "material": reading.material,
        "target_kg": reading.target_kg,
        "actual_kg": reading.actual_kg,
        "deviation_percent": reading.deviation_percent,
        "ok": reading.ok,
    }


def summarise_reports(reports: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    """Fold several weigh reports into one summary."""

    return {
        "reports": [dict(report) for report in reports],
        "count": len(reports),
        "worst_deviation_percent": max(
            (float(report.get("deviation_percent", 0.0)) for report in reports), default=0.0
        ),
    }
