"""A small path router for the console."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..errors import MethodNotAllowedError, NotFoundError, ValidationError

Handler = Callable[["Request"], "Response"]


@dataclass(frozen=True, slots=True)
class Request:
    """One inbound call."""

    method: str
    path: str
    query: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    body: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    params: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def field(self, name: str, default: Any = None) -> Any:
        """Return a body field, falling back to the query string."""

        if name in self.body:
            return self.body[name]
        return self.query.get(name, default)

    def require_field(self, name: str) -> Any:
        """Return a body field or refuse the call."""

        value = self.field(name)
        if value is None or value == "":
            raise ValidationError("field is required", field=name, path=self.path)
        return value

    def with_params(self, params: Mapping[str, str]) -> "Request":
        return Request(method=self.method, path=self.path, query=self.query, body=self.body, params=params)


@dataclass(frozen=True, slots=True)
class Response:
    """One outbound result."""

    status: int
    text: str
    content_type: str = "application/json; charset=utf-8"

    @classmethod
    def json(cls, payload: Any, status: int = 200) -> "Response":
        from .response import encode_json

        return cls(status=status, text=encode_json(payload), content_type="application/json; charset=utf-8")

    @classmethod
    def html(cls, text: str, status: int = 200) -> "Response":
        return cls(status=status, text=text, content_type="text/html; charset=utf-8")

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


@dataclass(frozen=True, slots=True)
class Route:
    """A method, a pattern and the handler behind it."""

    method: str
    pattern: str
    handler: Handler

    def match_path(self, path: str) -> Mapping[str, str] | None:
        """Return the captured parameters when ``path`` fits the pattern."""

        expected = _segments(self.pattern)
        actual = _segments(path)
        if len(expected) != len(actual):
            return None
        captured: dict[str, str] = {}
        for pattern_part, path_part in zip(expected, actual):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                captured[pattern_part[1:-1]] = path_part
            elif pattern_part != path_part:
                return None
        return captured


def _segments(path: str) -> list[str]:
    stripped = path.strip("/")
    return [] if not stripped else stripped.split("/")


class Router:
    """Resolves a request into a handler."""

    __slots__ = ("_routes",)

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        if not pattern.startswith("/"):
            raise ValidationError("route pattern must start with a slash", pattern=pattern)
        self._routes.append(Route(method=method.upper(), pattern=pattern, handler=handler))

    def patterns(self) -> tuple[str, ...]:
        """Return every registered pattern."""

        return tuple(route.pattern for route in self._routes)

    def resolve(self, method: str, path: str) -> tuple[Route, Mapping[str, str]]:
        """Return the handler for ``method`` and ``path``."""

        verb = method.upper()
        matched_path = False
        for route in self._routes:
            params = route.match_path(path)
            if params is None:
                continue
            matched_path = True
            if route.method == verb:
                return route, params
        if not matched_path:
            for route in self._routes:
                if route.pattern == "/":
                    return route, {}
        if matched_path:
            raise MethodNotAllowedError("this path does not accept the verb", path=path, method=verb)
        raise NotFoundError("no route matches this path", path=path)

    def handle(self, request: Request) -> Response:
        """Resolve and run one request."""

        route, params = self.resolve(request.method, request.path)
        return route.handler(request.with_params(params))
