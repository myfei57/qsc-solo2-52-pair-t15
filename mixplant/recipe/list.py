"""The read model the recipe page renders."""

from __future__ import annotations

from typing import Any

from .book import RecipeBook
from .grade import catalogue


def describe_book(book: RecipeBook) -> dict[str, Any]:
    """Return the recipe listing plus the grade catalogue."""

    return {"recipes": book.describe(), "grades": catalogue(), "selected": book.selected_name()}
