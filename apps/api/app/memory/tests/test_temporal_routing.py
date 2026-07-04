"""Tier 1 — temporal/enumeration question routing (Fix 2). FREE, offline, no cognee.

engine.query_memory() reroutes clear temporal-enumeration questions ("what did I record today")
to list_memories over a computed UTC date range, instead of dead-ending on semantic query().
The classifier `_temporal_filters` is pure and deterministic given `now`, so we assert the
routing table and date boundaries directly, plus integration through query_memory with a
LocalStore. `now` is pinned so tests never depend on the wall clock.
"""

from datetime import datetime, timezone

import pytest

from app.memory import engine
from app.memory.stores.local_store import LocalStore
from app.schemas.memory import MemoryAnswer, MemoryEvent

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)  # a Saturday; Monday = 2026-06-29
PATIENT = "p_temporal"

TODAY_START = "2026-07-04T00:00:00+00:00"
TODAY_END = "2026-07-04T23:59:59.999999+00:00"


# --------------------------------------------------------------------------
# _temporal_filters — routes clear temporal-enumeration questions
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query,exp_from,exp_to,exp_label",
    [
        ("what did I record today", TODAY_START, TODAY_END, "today"),
        ("show me today's memories", TODAY_START, TODAY_END, "today"),
        ("what did I do today", TODAY_START, TODAY_END, "today"),
        ("everything from yesterday",
         "2026-07-03T00:00:00+00:00", "2026-07-03T23:59:59.999999+00:00", "yesterday"),
        ("what did I say yesterday",
         "2026-07-03T00:00:00+00:00", "2026-07-03T23:59:59.999999+00:00", "yesterday"),
        ("what did I record this week", "2026-06-29T00:00:00+00:00", TODAY_END, "this week"),
        ("list my memories this month", "2026-07-01T00:00:00+00:00", TODAY_END, "this month"),
        ("show me my memories from 2026-07-01",
         "2026-07-01T00:00:00+00:00", "2026-07-01T23:59:59.999999+00:00", "on 2026-07-01"),
        ("everything between 2026-07-01 and 2026-07-03",
         "2026-07-01T00:00:00+00:00", "2026-07-03T23:59:59.999999+00:00",
         "between 2026-07-01 and 2026-07-03"),
    ],
)
def test_temporal_questions_route_to_list(query, exp_from, exp_to, exp_label):
    route = engine._temporal_filters(query, NOW)
    assert route is not None, f"expected temporal routing for {query!r}"
    filters, label = route
    assert filters.date_from == exp_from
    assert filters.date_to == exp_to
    assert label == exp_label


# --------------------------------------------------------------------------
# _temporal_filters — leaves factual / relational / ambiguous on the normal path
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query",
    [
        "where is my wallet",            # factual -> CHUNKS/provenance
        "who is Ravi",                   # relational -> graph hybrid
        "did I take my medication today",  # temporal word but NO enumeration cue
        "what did I eat today",          # 'eat' not an enumeration verb
        "show me my wallet",             # enum cue but NO temporal term
        "list the medications",          # enum cue but NO temporal term
        "",                              # empty
    ],
)
def test_non_temporal_questions_stay_on_query(query):
    assert engine._temporal_filters(query, NOW) is None, f"{query!r} should NOT reroute"


# --------------------------------------------------------------------------
# Date-boundary inclusivity
# --------------------------------------------------------------------------
def _seed(store, specs):
    for eid, ts in specs:
        store.add_event(MemoryEvent(
            patient_id=PATIENT, event_id=eid, source="voice_note", recorded_at=ts,
            event_type="observation", transcript=f"note {eid}",
        ))


def test_today_boundaries_inclusive_and_exclusive():
    store = LocalStore()
    _seed(store, [
        ("evt_start", "2026-07-04T00:00:00Z"),      # today 00:00:00 -> INCLUDED
        ("evt_end", "2026-07-04T23:59:59Z"),        # today 23:59:59 -> INCLUDED
        ("evt_yest_edge", "2026-07-03T23:59:59Z"),  # yesterday 23:59:59 -> EXCLUDED
        ("evt_future", "2026-07-05T09:00:00Z"),     # tomorrow -> EXCLUDED
    ])
    ans = engine.query_memory(PATIENT, "what did I record today", store=store, now=NOW)
    got = {r.note_id for r in ans.results}
    assert got == {"evt_start", "evt_end"}, got


def test_this_week_includes_earlier_week_excludes_older_and_future():
    store = LocalStore()
    _seed(store, [
        ("evt_mon", "2026-06-29T09:00:00Z"),   # Monday (week start) -> INCLUDED
        ("evt_wed", "2026-07-01T09:00:00Z"),   # this week -> INCLUDED
        ("evt_today", "2026-07-04T09:00:00Z"), # today -> INCLUDED
        ("evt_lastweek", "2026-06-28T09:00:00Z"),  # Sunday before -> EXCLUDED
        ("evt_future", "2026-07-05T09:00:00Z"),    # after today -> EXCLUDED
    ])
    ans = engine.query_memory(PATIENT, "what did I record this week", store=store, now=NOW)
    got = {r.note_id for r in ans.results}
    assert got == {"evt_mon", "evt_wed", "evt_today"}, got


# --------------------------------------------------------------------------
# Integration through query_memory — same MemoryAnswer shape, calm phrasing
# --------------------------------------------------------------------------
def test_query_memory_today_returns_days_memories_chronologically():
    store = LocalStore()
    _seed(store, [
        ("evt_am", "2026-07-04T08:00:00Z"),
        ("evt_pm", "2026-07-04T20:00:00Z"),
        ("evt_yesterday", "2026-07-03T12:00:00Z"),
    ])
    ans = engine.query_memory(PATIENT, "what did I record today", store=store, now=NOW)
    assert isinstance(ans, MemoryAnswer)
    # Same contract shape as the semantic path.
    assert ans.query == "what did I record today" and ans.warnings == []
    assert [r.note_id for r in ans.results] == ["evt_am", "evt_pm"]  # chronological (asc)
    assert ans.answer.startswith("Here's what you recorded today:")


def test_query_memory_empty_day_is_calm_not_deadend():
    store = LocalStore()
    _seed(store, [("evt_old", "2026-06-01T09:00:00Z")])  # nothing today
    ans = engine.query_memory(PATIENT, "what did I record today", store=store, now=NOW)
    assert ans.results == []
    assert ans.answer.startswith("I don't have any memories recorded today")
    assert engine.EMPTY_RECALL_MESSAGE not in ans.answer  # not the semantic dead-end


def test_query_memory_factual_still_semantic():
    store = LocalStore()
    store.add_event(MemoryEvent(
        patient_id=PATIENT, event_id="evt_wallet", source="voice_note",
        recorded_at="2026-06-01T08:15:00Z", event_type="object_location",
        transcript="I kept my wallet on the kitchen counter.",
        entities={"objects": [{"name": "wallet", "location": "kitchen counter"}]},
    ))
    ans = engine.query_memory(PATIENT, "where is my wallet", store=store, now=NOW)
    assert any(r.note_id == "evt_wallet" for r in ans.results)
    assert "wallet" in ans.answer.lower()


def test_medication_route_matches_plural_medicines_query():
    store = LocalStore()
    store.add_event(MemoryEvent(
        patient_id=PATIENT,
        event_id="evt_tabs_6pm",
        source="voice_note",
        recorded_at="2026-07-04T18:00:00Z",
        event_type="medication_intake",
        transcript="I took my tablets at 6pm.",
        entities={"medications": [{"name": "tablets", "form": "tablet"}]},
    ))

    ans = engine.query_memory(PATIENT, "when did i take medicines", store=store, now=NOW)

    assert ans.results, "medication route should return the medication memory"
    assert ans.results[0].note_id == "evt_tabs_6pm"
    assert ans.results[0].node_type == "MedicationIntake"
    assert "6pm" in ans.answer.lower() or "took" in ans.answer.lower()


def test_medication_route_matches_plural_tablets_query():
    store = LocalStore()
    store.add_event(MemoryEvent(
        patient_id=PATIENT,
        event_id="evt_tabs_6pm",
        source="voice_note",
        recorded_at="2026-07-04T18:00:00Z",
        event_type="medication_intake",
        transcript="I took my tablets at 6pm.",
        entities={"medications": [{"name": "tablets", "form": "tablet"}]},
    ))

    ans = engine.query_memory(PATIENT, "when did i take tablets", store=store, now=NOW)

    assert ans.results and ans.results[0].note_id == "evt_tabs_6pm"
