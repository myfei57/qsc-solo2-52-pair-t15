"""Build the console router from the runtime."""

from __future__ import annotations

from typing import Any

from . import handlers_alarms, handlers_batch, handlers_cycle, handlers_discharge, handlers_plant, handlers_recipe
from .pages import PageStore
from .router import Router
from .server import ConsoleServer

BUILDERS = (
    handlers_plant.register,
    handlers_recipe.register,
    handlers_batch.register,
    handlers_cycle.register,
    handlers_discharge.register,
    handlers_alarms.register,
)


def build_router(runtime: Any, pages: PageStore) -> Router:
    """Register every console route."""

    router = Router()
    for builder in BUILDERS:
        builder(router, runtime, pages)
    return router


def build_server(runtime: Any, *, pages_dir: str | None = None) -> ConsoleServer:
    """Build the console server for ``runtime``."""

    pages = PageStore(pages_dir or runtime.config.web_dir)
    return ConsoleServer(runtime, pages=pages)
