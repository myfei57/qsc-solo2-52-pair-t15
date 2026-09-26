"""HTTP transport for the console."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..errors import MixPlantError, ValidationError
from .pages import PageStore
from .router import Request, Response, Router


class _Handler(BaseHTTPRequestHandler):
    """Translates HTTP calls into router calls."""

    server_version = "mixplant/0.3"
    protocol_version = "HTTP/1.1"

    router: Router
    pages: PageStore

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server contract
        """Keep the console output free of request noise."""

    def do_GET(self) -> None:  # noqa: N802 - http.server contract
        self._run("GET")

    def do_POST(self) -> None:  # noqa: N802 - http.server contract
        self._run("POST")

    def _run(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            body = self._read_body() if method == "POST" else {}
            response = self.router.handle(Request(method=method, path=parsed.path, query=query, body=body))
        except MixPlantError as error:
            response = Response.json(error.as_payload(), status=error.http_status)
        except Exception as error:  # pragma: no cover - defensive
            response = Response.json(
                {"code": "internal_error", "message": str(error), "context": {}},
                status=500,
            )
        self._send(response)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError("request body is not valid json") from exc
        if not isinstance(payload, dict):
            raise ValidationError("request body must be a json object")
        return payload

    def _send(self, response: Response) -> None:
        payload = response.text.encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class ConsoleServer:
    """Binds the console to a port and runs it on demand."""

    __slots__ = ("runtime", "pages", "router", "_server", "_thread", "_host", "_port")

    def __init__(
        self,
        runtime: Any,
        *,
        host: str | None = None,
        port: int | None = None,
        pages: PageStore | None = None,
    ) -> None:
        from .run import build_router

        self.runtime = runtime
        self.pages = pages or PageStore(runtime.config.web_dir)
        self.router = build_router(runtime, self.pages)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._host = host or runtime.config.host
        self._port = runtime.config.port if port is None else port

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        if self._server is None:
            return self._port
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self.port}"

    def bind(self) -> None:
        """Create the listening socket."""

        if self._server is not None:
            return
        handler = type("BoundHandler", (_Handler,), {"router": self.router, "pages": self.pages})
        server = ThreadingHTTPServer((self._host, self._port), handler)
        server.daemon_threads = True
        self._server = server

    def serve_forever(self) -> None:
        """Serve until ``stop`` is called."""

        self.bind()
        assert self._server is not None
        self._server.serve_forever()

    def start_background(self) -> threading.Thread:
        """Serve on a background thread and return it."""

        self.bind()
        thread = threading.Thread(target=self._serve_thread, name="plant-console", daemon=True)
        thread.start()
        self._thread = thread
        return thread

    def _serve_thread(self) -> None:
        assert self._server is not None
        self._server.serve_forever()

    def handle(self, request: Request) -> Response:
        """Run one request without going through a socket."""

        try:
            return self.router.handle(request)
        except MixPlantError as error:
            return Response.json(error.as_payload(), status=error.http_status)

    def stop(self) -> None:
        """Release the port."""

        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
