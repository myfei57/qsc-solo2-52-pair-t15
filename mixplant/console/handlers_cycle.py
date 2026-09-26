"""Routes for the mixing cycle and the metering commands."""

from __future__ import annotations

from typing import Any

from .router import Request, Response, Router

COMMANDS = (
    ("POST", "/api/cement/silo", "cement.load_silo"),
    ("POST", "/api/cement/gate", "cement.open_gate"),
    ("POST", "/api/cement/gate/close", "cement.close_gate"),
    ("POST", "/api/water/valve", "water.open_valve"),
    ("POST", "/api/water/dispense", "water.dispense"),
    ("POST", "/api/water/prime", "water.prime"),
    ("POST", "/api/mix/start", "mix.start"),
    ("POST", "/api/mix/feed", "mix.feed"),
    ("POST", "/api/mix/time", "mix.time"),
    ("POST", "/api/mix/finish", "mix.finish"),
    ("POST", "/api/mix/schedule", "mix.schedule"),
    ("POST", "/api/mix/stop", "mix.stop"),
    ("POST", "/api/clock/advance", "clock.advance"),
    ("POST", "/api/snapshot", "snapshot.take"),
    ("POST", "/api/rollback", "store.rollback"),
)


def register(router: Router, runtime: Any, pages: Any) -> None:
    """Register the cycle routes."""

    router.add("GET", "/api/cycle", lambda _: Response.json(runtime.controller.mix_view()))
    for method, path, command in COMMANDS:
        router.add(method, path, _command(runtime, command))


def _command(runtime: Any, command: str):
    def handler(request: Request) -> Response:
        return Response.json(runtime.dispatch(command, dict(request.body)))

    return handler
