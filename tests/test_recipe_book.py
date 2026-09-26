"""Recipe publishing, selection, versioning and batching plans."""

from __future__ import annotations

import pytest

from mixplant.config import Limits
from mixplant.errors import DuplicateError, NotFoundError, ValidationError
from mixplant.ns.topology import default_topology
from mixplant.recipe.book import RecipeBook
from mixplant.recipe.grade import grade_for
from mixplant.recipe.mapping import build_mapping, require_fresh
from mixplant.recipe.plan import plan_batch
from mixplant.recipe.recipe import Recipe
from mixplant.recipe.validate import require_valid, validate_recipe
from mixplant.recipe.version import require_current, stamp_of


def _recipe(version: int = 1) -> Recipe:
    return Recipe(
        name="mix-a",
        grade=grade_for("C30"),
        version=version,
        factors={"sand": 760.0, "cement": 330.0, "water": 175.0},
        mix_time_ticks=6,
        moisture_ref_percent=4.5,
    )


def test_book_refuses_a_reused_version() -> None:
    book = RecipeBook()
    book.publish(_recipe(1))
    with pytest.raises(DuplicateError):
        book.publish(_recipe(1))


def test_book_selects_the_newest_version() -> None:
    book = RecipeBook()
    book.publish(_recipe(1))
    book.publish(_recipe(2))
    assert book.select("mix-a").version == 2
    assert book.selected_name() == "mix-a"
    with pytest.raises(NotFoundError):
        book.current("missing")


def test_recipe_requires_positive_factors() -> None:
    with pytest.raises(ValidationError):
        Recipe(
            name="mix-a",
            grade=grade_for("C30"),
            version=1,
            factors={"sand": 0.0},
            mix_time_ticks=6,
            moisture_ref_percent=4.5,
        )


def test_validation_flags_a_high_moisture_reference() -> None:
    recipe = _recipe()
    findings = validate_recipe(recipe, Limits(moisture_max_percent=2.0))
    require_valid([finding for finding in findings if finding.code != "moisture_reference"])
    assert [finding.ok for finding in findings if finding.code == "moisture_reference"] == [False]


def test_plan_scales_and_compensates() -> None:
    plan = plan_batch(_recipe(), batch_id="B-1", quantity=2.0, moisture_percent=5.0)
    assert plan.material_mass("sand") == pytest.approx(760 * 2 * 1.05)
    assert plan.material_mass("cement") == pytest.approx(660.0)
    assert plan.free_water_l == pytest.approx(76.0)


def test_mapping_is_bound_to_the_recipe_version() -> None:
    mapping = build_mapping(_recipe(3), default_topology())
    assert mapping.bin_of("cement") == "silo-1"
    assert mapping.bin_of("water") == "tank-1"
    require_fresh(mapping, 3, action="agg.weigh")
    with pytest.raises(Exception):
        require_fresh(mapping, 4, action="agg.weigh")


def test_version_stamp_detects_a_stale_plan() -> None:
    recipe = _recipe(2)
    assert stamp_of(recipe).version == 2
    require_current(recipe, 2, action="agg.weigh")
    with pytest.raises(Exception):
        require_current(recipe, 3, action="agg.weigh")
