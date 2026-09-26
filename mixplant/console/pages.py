"""Reader for the static console pages."""

from __future__ import annotations

from pathlib import Path

from ..errors import NotFoundError

PAGES: dict[str, str] = {
    "recipe": "recipe.html",
    "batch": "batch.html",
    "discharge": "discharge.html",
    "alarms": "alarms.html",
}


class PageStore:
    """Loads the static pages from one directory."""

    __slots__ = ("_directory",)

    def __init__(self, directory: Path | str) -> None:
        self._directory = Path(directory)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(PAGES))

    def path_for(self, name: str) -> Path:
        filename = PAGES.get(name)
        if filename is None:
            raise NotFoundError("unknown page", page=name, known=list(PAGES))
        return self._directory / filename

    def load(self, name: str) -> str:
        path = self.path_for(name)
        if not path.exists():
            raise NotFoundError("page file is missing", page=name, path=str(path))
        return path.read_text(encoding="utf-8")
