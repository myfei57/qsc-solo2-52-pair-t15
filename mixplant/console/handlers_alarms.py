"""Routes for the alarm page, the audit ledger and the versioned artifacts."""

from __future__ import annotations

from typing import Any

from .response import inject_snapshot
from .router import Request, Response, Router

COMMANDS = (
    ("POST", "/api/audit/note", "audit.note"),
    ("POST", "/api/audit/rollup", "audit.rollup"),
    ("POST", "/api/baseline", "baseline.publish"),
    ("POST", "/api/confirmation", "confirmation.take"),
)


def register(router: Router, runtime: Any, pages: Any) -> None:
    """Register the alarm and audit routes."""

    router.add(
        "GET",
        "/pages/alarms",
        lambda _: Response.html(inject_snapshot(pages.load("alarms"), runtime.controller.alarm_view())),
    )
    router.add("GET", "/api/alarms", lambda _: Response.json(runtime.controller.alarm_view()))
    for method, path, command in COMMANDS:
        router.add(method, path, _command(runtime, command))


def _command(runtime: Any, command: str):
    def handler(request: Request) -> Response:
        return Response.json(runtime.dispatch(command, dict(request.body)))

    return handler
