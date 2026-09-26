"""Routes for the discharge page, the truck queue and the delivery line."""

from __future__ import annotations

from typing import Any

from .confirm import confirm_payload, require_volume
from .response import inject_snapshot
from .router import Request, Response, Router

COMMANDS = (
    ("POST", "/api/chute/arrive", "chute.arrive"),
    ("POST", "/api/chute/open", "chute.open"),
    ("POST", "/api/chute/load", "chute.load"),
    ("POST", "/api/chute/close", "chute.close"),
    ("POST", "/api/pump/prime", "pump.prime"),
    ("POST", "/api/pump/start", "pump.start"),
    ("POST", "/api/pump/stroke", "pump.stroke"),
    ("POST", "/api/pump/pressure", "pump.pressure"),
    ("POST", "/api/pump/finish", "pump.finish"),
    ("POST", "/api/sampler/draw", "sampler.draw"),
    ("POST", "/api/sampler/release", "sampler.release"),
    ("POST", "/api/sampler/file", "sampler.file"),
)


def register(router: Router, runtime: Any, pages: Any) -> None:
    """Register the discharge routes."""

    router.add(
        "GET",
        "/pages/discharge",
        lambda _: Response.html(inject_snapshot(pages.load("discharge"), runtime.controller.discharge_view())),
    )
    router.add("GET", "/api/discharge", lambda _: Response.json(runtime.controller.discharge_view()))
    router.add("POST", "/api/chute/confirm", _confirm(runtime))
    for method, path, command in COMMANDS:
        router.add(method, path, _command(runtime, command))


def _confirm(runtime: Any):
    def handler(request: Request) -> Response:
        payload = confirm_payload(dict(request.body))
        require_volume(float(payload["volume_m3"]))
        return Response.json(runtime.dispatch("chute.confirm", payload))

    return handler


def _command(runtime: Any, command: str):
    def handler(request: Request) -> Response:
        return Response.json(runtime.dispatch(command, dict(request.body)))

    return handler
