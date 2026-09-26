"""Self checks the console can run without touching the plant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Finding:
    """One diagnostic result."""

    code: str
    ok: bool
    detail: str

    def describe(self) -> dict[str, Any]:
        return {"code": self.code, "ok": self.ok, "detail": self.detail}


def check_rule_table(*, names: Sequence[str], actions: Sequence[str]) -> Finding:
    """The rule table must be uniquely named and address real actions."""

    duplicated = sorted({name for name in names if list(names).count(name) > 1})
    unnamed = [action for action in actions if not action]
    ok = not duplicated and not unnamed
    if ok:
        detail = f"{len(names)} rules across {len(set(actions))} actions"
    else:
        detail = f"duplicated {duplicated}, unnamed {len(unnamed)}"
    return Finding(code="interlock_table", ok=ok, detail=detail)


def check_lines_hydrated(*, machines: Mapping[str, Any]) -> Finding:
    """Every line must sit at a declared stage after a restart."""

    missing = [name for name, machine in machines.items() if machine.phase not in machine.order()]
    return Finding(
        code="line_hydration",
        ok=not missing,
        detail="every line sits at a declared stage" if not missing else f"lines off sequence: {missing}",
    )


def check_watermark(*, committed: int, durable: int) -> Finding:
    """The commit watermark may never run ahead of the durable one."""

    return Finding(
        code="watermark_order",
        ok=committed <= durable,
        detail=f"committed {committed} against durable {durable}",
    )


def run_diagnostics(
    *,
    rule_names: Sequence[str],
    rule_actions: Sequence[str],
    machines: Mapping[str, Any],
    watermark: Mapping[str, Any],
) -> dict[str, Any]:
    """Run every check and fold the results into one document."""

    findings = [
        check_rule_table(names=rule_names, actions=rule_actions),
        check_lines_hydrated(machines=machines),
        check_watermark(
            committed=int(watermark.get("committed_seq", 0)),
            durable=int(watermark.get("durable_seq", 0)),
        ),
    ]
    return {
        "ok": all(finding.ok for finding in findings),
        "findings": [finding.describe() for finding in findings],
    }
