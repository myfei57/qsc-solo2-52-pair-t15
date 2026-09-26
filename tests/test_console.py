"""The console routes, page loading and error mapping."""

from __future__ import annotations

import json
import urllib.request

from mixplant.console.pages import PAGES, PageStore
from mixplant.console.response import SNAPSHOT_PLACEHOLDER, encode_json, inject_snapshot
from mixplant.console.router import Request, Response, Router
from mixplant.console.run import build_router, build_server
from mixplant.console.confirm import confirm_payload, require_volume
from mixplant.console.server import ConsoleServer
from mixplant.errors import NotFoundError, ValidationError
from mixplant.runtime import PlantRuntime
from tests.support import publish_and_select


def test_pages_are_declared() -> None:
    assert set(PAGES) == {"recipe", "batch", "discharge", "alarms"}


def test_every_page_renders_with_live_state(runtime: PlantRuntime) -> None:
    store = PageStore(runtime.config.web_dir)
    assert store.names() == ("alarms", "batch", "discharge", "recipe")
    for name in store.names():
        page = store.load(name)
        rendered = inject_snapshot(page, runtime.state())
        assert "<!DOCTYPE html>" in rendered
        assert SNAPSHOT_PLACEHOLDER not in rendered
        assert store.path_for(name).name == PAGES[name]


def test_router_captures_parameters() -> None:
    router = Router()
    router.add("GET", "/api/trucks/{truck}", lambda request: Response.json({"truck": request.params["truck"]}))
    response = router.handle(Request(method="GET", path="/api/trucks/T-01"))
    assert json.loads(response.text) == {"truck": "T-01"}
    assert router.patterns() == ("/api/trucks/{truck}",)


def test_router_refuses_an_unknown_path() -> None:
    router = Router()
    try:
        router.resolve("GET", "/missing")
    except NotFoundError as error:
        assert error.http_status == 404
    else:  # pragma: no cover - the call above has to raise
        raise AssertionError("expected a NotFoundError")


def test_router_reports_a_wrong_verb(runtime: PlantRuntime) -> None:
    server = ConsoleServer(runtime, pages=PageStore(runtime.config.web_dir))
    response = server.handle(Request(method="POST", path="/api/health"))
    assert response.status == 405
    assert json.loads(response.text)["code"] == "method_not_allowed"


def test_response_reports_ok_and_encodes_json() -> None:
    response = Response.json({"b": 1, "a": 2})
    assert response.ok is True
    assert json.loads(encode_json({"b": 1, "a": 2})) == {"a": 2, "b": 1}
    assert json.loads(response.text) == {"a": 2, "b": 1}


def test_snapshot_injection_uses_the_placeholder() -> None:
    page = f"<html>{SNAPSHOT_PLACEHOLDER}</html>"
    rendered = inject_snapshot(page, {"tick": 3})
    assert SNAPSHOT_PLACEHOLDER not in rendered
    assert '"tick": 3' in rendered.replace("\n", " ")


def test_page_store_reports_a_missing_page(tmp_path) -> None:
    store = PageStore(tmp_path)
    try:
        store.load("recipe")
    except NotFoundError as error:
        assert error.code == "not_found"
    else:  # pragma: no cover
        raise AssertionError("expected a missing page")


def test_console_serves_state_and_commands(runtime: PlantRuntime) -> None:
    server = ConsoleServer(runtime, pages=PageStore(runtime.config.web_dir))
    health = server.handle(Request(method="GET", path="/api/health"))
    assert health.ok is True
    publish_and_select(runtime)
    recipes = server.handle(Request(method="GET", path="/api/recipes"))
    assert json.loads(recipes.text)["book"]["selected"] == "mix-a"
    for path in ("/api/batch", "/api/cycle", "/api/discharge", "/api/alarms", "/api/state", "/api/plant"):
        assert server.handle(Request(method="GET", path=path)).status == 200
    assert server.handle(Request(method="GET", path="/api/diagnostics")).ok is True


def test_console_returns_a_validation_error(runtime: PlantRuntime) -> None:
    server = ConsoleServer(runtime, pages=PageStore(runtime.config.web_dir))
    response = server.handle(Request(method="POST", path="/api/agg/drop", body={}))
    assert response.status in (400, 409)


def test_console_builds_a_bound_server(runtime: PlantRuntime, tmp_path) -> None:
    server = build_server(runtime)
    assert server.router is not None
    assert build_router(runtime, PageStore(tmp_path)).patterns()


def test_console_serves_over_a_real_socket(runtime: PlantRuntime) -> None:
    server = ConsoleServer(runtime, host="127.0.0.1", port=0, pages=PageStore(runtime.config.web_dir))
    server.start_background()
    try:
        with urllib.request.urlopen(f"{server.url}/api/health", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "ok"
    finally:
        server.stop()


def test_confirm_payload_is_validated() -> None:
    payload = confirm_payload({"truck_id": "T-01", "volume_m3": 6})
    assert require_volume(float(payload["volume_m3"])) == 6.0
    try:
        confirm_payload({"truck_id": "", "volume_m3": 6})
    except ValidationError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected a ValidationError")
