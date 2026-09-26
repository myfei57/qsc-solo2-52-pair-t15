"""Record queries and the derived state view."""

from __future__ import annotations

import pytest

from mixplant.clock import ManualClock
from mixplant.decision.query import RecordQuery, query_from_params, run_query
from mixplant.decision.stateview import StateView
from mixplant.errors import ValidationError
from mixplant.ids import SequenceIds
from mixplant.store.repository import RecordRepository
from tests.support import batch_and_weigh, run


def _store() -> RecordRepository:
    clock = ManualClock()
    store = RecordRepository.in_memory(clock, SequenceIds())
    clock.advance(1)
    store.publish("agg.weigh", "agg", 1, {"active": True, "actual_kg": 4800})
    clock.advance(1)
    store.publish("agg.persist", "agg", 1, {"active": True})
    clock.advance(1)
    store.publish("mix.mixer", "mix", 1, {"active": True})
    return store


def test_query_filters_by_kind_and_origin() -> None:
    store = _store()
    result = run_query(store.committed_records(), RecordQuery(kind="agg.weigh"))
    assert result.matched == 1
    assert result.describe()["rows"][0]["kind"] == "agg.weigh"
    by_origin = run_query(store.committed_records(), RecordQuery(origin="mix"))
    assert by_origin.matched == 1


def test_query_limits_the_newest_rows() -> None:
    store = _store()
    result = run_query(store.committed_records(), RecordQuery(limit=2))
    assert [row.kind for row in result.rows] == ["agg.persist", "mix.mixer"]


def test_query_parameters_are_parsed() -> None:
    query = query_from_params({"kind": "agg.weigh", "limit": "5", "tombstones": "true"})
    assert query.kind == "agg.weigh"
    assert query.limit == 5
    assert query.include_tombstones is True
    with pytest.raises(ValidationError):
        query_from_params({"limit": "0"})


def test_state_view_reports_facts_and_history() -> None:
    store = _store()
    view = StateView(store)
    assert view.facts()["agg.weight_persisted"] is True
    assert view.latest_payload("mix.mixer") == {"active": True}
    delta = view.delta(0)
    assert "agg.weigh" in delta.describe()["appeared"]


def test_runtime_exposes_the_history_delta(runtime) -> None:
    batch_and_weigh(runtime)
    run(runtime, "clock.advance", {"ticks": 3})
    run(runtime, "agg.release", {"residual_kg": 2.0})
    history = runtime.history(0)
    assert history["delta"]["appeared"]
    assert history["state"]
