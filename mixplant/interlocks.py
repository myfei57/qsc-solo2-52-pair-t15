"""The rule table every action is checked against."""

from __future__ import annotations

from .facts import (
    BIN_MAPPED,
    CEMENT_FED,
    CHUTE_OPEN,
    HOPPER_RELEASED,
    MIXER_RUNNING,
    MIX_TIMED,
    MOIST_COMPENSATED,
    PUMP_RUNNING,
    RECIPE_PUBLISHED,
    RECIPE_SELECTED,
    SAMPLER_LATCHED,
    TRUCK_LOADED,
    WATER_DISPENSED,
    WATER_PRIMED,
    WEIGHT_PERSISTED,
)
from .statemachine.interlock import InterlockEngine, InterlockRule

DEFAULT_RULES: tuple[InterlockRule, ...] = (
    InterlockRule(
        name="recipe-select-needs-book",
        action="recipe.select",
        requires=(RECIPE_PUBLISHED,),
        message="a recipe must be published before one can be selected",
    ),
    InterlockRule(
        name="agg-map-needs-selection",
        action="agg.map_bin",
        requires=(RECIPE_SELECTED,),
        message="bins are mapped for the recipe that is going to be batched",
    ),
    InterlockRule(
        name="agg-weigh-needs-mapping",
        action="agg.weigh",
        requires=(RECIPE_SELECTED, BIN_MAPPED),
        message="weighing needs a selected recipe and a refreshed bin mapping",
    ),
    InterlockRule(
        name="agg-persist-needs-weighing",
        action="agg.persist",
        requires=(RECIPE_SELECTED,),
        message="a weight is only durable for the recipe it was weighed against",
    ),
    InterlockRule(
        name="agg-check-needs-compensation",
        action="agg.check",
        requires=(MOIST_COMPENSATED,),
        message="the dry weight may only be checked after the moisture is compensated",
    ),
    InterlockRule(
        name="agg-drop-needs-durable-weight",
        action="agg.drop",
        requires=(WEIGHT_PERSISTED,),
        message="material may only be dropped once the weight is durable",
    ),
    InterlockRule(
        name="agg-release-needs-weighing",
        action="agg.release",
        requires=(RECIPE_SELECTED,),
        message="the scale hopper is released after the weights of a batch",
    ),
    InterlockRule(
        name="cement-feed-needs-water",
        action="cement.feed",
        requires=(WATER_DISPENSED,),
        message="the binder is washed in after the batching water",
    ),
    InterlockRule(
        name="mix-water-needs-mixer",
        action="mix.water_in",
        requires=(MIXER_RUNNING,),
        message="water is only metered into a running mixer",
    ),
    InterlockRule(
        name="mix-cement-needs-water",
        action="mix.cement_in",
        requires=(WATER_DISPENSED,),
        message="the cement is fed after the water so it cannot cake on the shaft",
    ),
    InterlockRule(
        name="mix-time-needs-inputs",
        action="mix.time",
        requires=(MIXER_RUNNING, CEMENT_FED),
        message="the mixing window starts once every input is in the drum",
    ),
    InterlockRule(
        name="mix-stop-needs-empty-hopper",
        action="mix.stop",
        requires=(HOPPER_RELEASED,),
        message="the mixer may only stop after the batch scales are released",
    ),
    InterlockRule(
        name="chute-open-needs-mixed",
        action="chute.open",
        requires=(MIX_TIMED,),
        message="the discharge door needs a finished mixing window",
    ),
    InterlockRule(
        name="chute-load-needs-open-door",
        action="chute.load",
        requires=(CHUTE_OPEN,),
        message="trucks are loaded through an open discharge door",
    ),
    InterlockRule(
        name="chute-confirm-needs-load",
        action="chute.confirm",
        requires=(TRUCK_LOADED,),
        message="a truck can only be confirmed after it was loaded",
    ),
    InterlockRule(
        name="chute-close-needs-open-door",
        action="chute.close",
        requires=(CHUTE_OPEN,),
        message="only an open door can be closed",
    ),
    InterlockRule(
        name="pump-start-needs-prime",
        action="pump.start",
        requires=(WATER_PRIMED,),
        message="the pump may not start before the delivery line is primed",
    ),
    InterlockRule(
        name="pump-stroke-needs-running-pump",
        action="pump.stroke",
        requires=(PUMP_RUNNING,),
        message="only a running pump delivers strokes",
    ),
    InterlockRule(
        name="sampler-draw-needs-mixed",
        action="sampler.draw",
        requires=(MIX_TIMED,),
        forbids=(SAMPLER_LATCHED,),
        message="a sample needs a finished mix and a released draw latch",
    ),
    InterlockRule(
        name="sampler-release-needs-latch",
        action="sampler.reset",
        requires=(SAMPLER_LATCHED,),
        message="only a set latch can be released",
    ),
)


def build_engine(rules: tuple[InterlockRule, ...] | None = None) -> InterlockEngine:
    """Build the interlock engine, optionally with a replaced rule table."""

    return InterlockEngine(DEFAULT_RULES if rules is None else rules)
