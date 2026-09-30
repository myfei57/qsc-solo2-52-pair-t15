"""Routes for per subscriber replay progress and the foreground catch up."""

from __future__ import annotations

from typing import Any

from .router import Request, Response, Router


def register(router: Router, runtime: Any, pages: Any) -> None:
    """Register the subscription routes."""

    router.add(
        "GET",
        "/api/subscriptions",
        lambda _: Response.json(runtime.subscription_progress()),
    )
    router.add("POST", "/api/subscriptions/replay", _replay(runtime))


def _replay(runtime: Any):
    def handler(request: Request) -> Response:
        subscriber = request.field("subscriber")
        report = runtime.replay_subscriptions(None if subscriber in (None, "") else str(subscriber))
        # Replay is a foreground catch up: 200 when it caught everything up,
        # 409 while a gap remains, so the caller can see it is not done.
        status = 200 if report["complete"] else 409
        return Response.json(report, status=status)

    return handler
