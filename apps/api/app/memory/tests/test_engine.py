"""Tests for the memory engine (Slice 5), using an injected LocalStore."""

from datetime import datetime, timezone

import pytest

from app.memory import engine
from app.memory.engine import EMPTY_RECALL_MESSAGE
from app.memory.seed import BLUE_PILL_1_ID, PATIENT_ID, baseline_events, load_baseline
from app.memory.stores.local_store import LocalStore
from app.schemas.memory import ListFilters, MemoryAnswer, MemoryEvent, MemoryResult


@pytest.fixture()
def store() -> LocalStore:
    return LocalStore()


def _wallet_event() -> MemoryEvent:
    return MemoryEvent(
        patient_id=PATIENT_ID,
        recorded_at="2026-07-01T08:15:00Z",
        event_type="object_location",
        transcript="I kept my wallet near the TV.",
        entities={"objects": [{"name": "wallet", "location": "near the TV"}]},
    )


def _intake(event_id: str, recorded_at: str) -> MemoryEvent:
    return MemoryEvent(
        patient_id=PATIENT_ID,
        event_id=event_id,
        recorded_at=recorded_at,
        event_type="medication_intake",
        entities={"medications": [{"name": "blue pill"}]},
    )


# -- ingest -------------------------------------------------------------------


def test_ingest_generates_id_and_is_queryable(store: LocalStore):
    result = engine.ingest_memory_event(_wallet_event(), store=store)
    assert result["event_id"].startswith("evt_")
    assert result["status"] == "stored"
    assert result["warning"] is None

    answer = engine.query_memory(PATIENT_ID, "where is my wallet", store=store)
    assert answer.results
    assert answer.results[0].note_id == result["event_id"]


def test_ingest_double_dose_returns_warning(store: LocalStore):
    engine.ingest_memory_event(_intake("evt_a", "2026-07-01T08:30:00Z"), store=store)
    result = engine.ingest_memory_event(_intake("evt_b", "2026-07-01T09:10:00Z"), store=store)
    warning = result["warning"]
    assert warning is not None
    assert warning.type == "possible_double_dose"
    assert {"evt_a", "evt_b"} <= set(warning.related_note_ids)


# -- query --------------------------------------------------------------------


def test_query_returns_full_provenance(store: LocalStore):
    load_baseline(store)
    answer = engine.query_memory(PATIENT_ID, "where is my wallet", store=store)
    assert isinstance(answer, MemoryAnswer)
    assert answer.query == "where is my wallet"
    assert answer.warnings == []
    assert answer.results

    top = answer.results[0]
    assert top.fact
    assert top.node_type == "ObjectLocation"
    assert top.recorded_at
    assert top.source == "voice_note"
    assert top.verification_status == "unverified"
    assert top.note_id
    # calm answer reflects the (unverified) caregiver status
    assert "caregiver" in answer.answer.lower()
    assert "wallet" in answer.answer.lower()


def test_query_empty_recall_is_deterministic(store: LocalStore):
    load_baseline(store)
    answer = engine.query_memory(PATIENT_ID, "xyzzy quux", store=store)
    assert answer.results == []
    assert answer.answer == EMPTY_RECALL_MESSAGE


def test_query_reflects_confirmed_status(store: LocalStore):
    load_baseline(store)
    wallet_id = engine.query_memory(PATIENT_ID, "where is my wallet", store=store).results[0].note_id
    assert engine.verify_memory(PATIENT_ID, wallet_id, "confirmed", "nurse_amy", store=store) is True

    answer = engine.query_memory(PATIENT_ID, "where is my wallet", store=store)
    assert answer.results[0].verification_status == "confirmed"
    assert "confirmed" in answer.answer.lower()
    assert "nurse_amy" in answer.answer


def test_query_kinship_answer_is_relation_specific(store: LocalStore):
    engine.ingest_memory_event(
        MemoryEvent(
            patient_id=PATIENT_ID,
            recorded_at="2026-07-04T09:00:00Z",
            event_type="person_mention",
            transcript="My son Ravi came to visit me. He visits every Sunday.",
            entities={"people": [{"name": "Ravi", "relationship": "son"}]},
        ),
        store=store,
    )

    answer = engine.query_memory(PATIENT_ID, "Who is my son?", store=store)
    assert answer.results
    assert answer.answer.lower().startswith("ravi is your son")


def test_query_medication_today_ignores_unrelated_today_notes(store: LocalStore):
    engine.ingest_memory_event(
        MemoryEvent(
            patient_id=PATIENT_ID,
            recorded_at="2026-07-04T08:15:00Z",
            event_type="person_mention",
            transcript="My mom came to visit me today and we watched a movie.",
            entities={"people": [{"name": "Mom", "relationship": "mother"}], "time_reference": "today"},
        ),
        store=store,
    )
    engine.ingest_memory_event(
        MemoryEvent(
            patient_id=PATIENT_ID,
            recorded_at="2026-07-04T08:30:00Z",
            event_type="medication_intake",
            transcript="I took my blue pill after breakfast today.",
            entities={
                "medications": [{"name": "blue pill", "form": "tablet"}],
                "time_reference": "today",
            },
        ),
        store=store,
    )

    answer = engine.query_memory(
        PATIENT_ID,
        "Did I take my medicine today?",
        store=store,
        now=datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert answer.results
    assert all(row.node_type == "MedicationIntake" for row in answer.results)
    assert "blue pill" in answer.results[0].fact.lower()


def test_query_uses_llm_synthesis_when_available(store: LocalStore, monkeypatch):
    engine.ingest_memory_event(
        MemoryEvent(
            patient_id=PATIENT_ID,
            recorded_at="2026-07-04T09:00:00Z",
            event_type="person_mention",
            transcript="My son Ravi came to visit me.",
            entities={"people": [{"name": "Ravi", "relationship": "son"}]},
        ),
        store=store,
    )

    monkeypatch.setattr(
        engine,
        "_maybe_llm_answer",
        lambda query, rows: "LLM: Ravi is your son and visits often." if rows else None,
    )

    answer = engine.query_memory(PATIENT_ID, "Tell me about Ravi", store=store)
    assert answer.results
    assert answer.answer == "LLM: Ravi is your son and visits often."


# -- verify / consolidate / forget / graph ------------------------------------


def test_verify_memory_missing_returns_false(store: LocalStore):
    load_baseline(store)
    assert engine.verify_memory(PATIENT_ID, "nope", "confirmed", "x", store=store) is False


def test_consolidate_surfaces_pattern(store: LocalStore):
    load_baseline(store)
    out = engine.consolidate(PATIENT_ID, store=store)
    assert "run_id" in out
    assert len(out["patterns"]) == 1
    assert out["patterns"][0]["count"] == 3


def test_forget_memory(store: LocalStore):
    load_baseline(store)
    assert engine.forget_memory(PATIENT_ID, BLUE_PILL_1_ID, store=store) is True
    rows = engine.query_memory(PATIENT_ID, "blue pill", store=store).results
    assert all(r.note_id != BLUE_PILL_1_ID for r in rows)


def test_graph_delegates(store: LocalStore):
    load_baseline(store)
    g = engine.graph(PATIENT_ID, store=store)
    assert g["nodes"]
    assert any(n["type"] == "Patient" for n in g["nodes"])


# -- list_memories (Slice 8c wrapper) -----------------------------------------


def test_list_memories_delegates(store: LocalStore):
    load_baseline(store)

    # no filters -> every baseline event, as MemoryResult rows with provenance
    all_rows = engine.list_memories(PATIENT_ID, store=store)
    assert len(all_rows) == len(baseline_events())
    assert all(isinstance(r, MemoryResult) for r in all_rows)
    assert all(r.note_id and r.recorded_at and r.source for r in all_rows)

    # filters / sort / limit are passed straight through to the store
    meds = engine.list_memories(
        PATIENT_ID, ListFilters(event_type="medication_intake"), store=store
    )
    assert [r.node_type for r in meds] == ["MedicationIntake"]

    limited = engine.list_memories(PATIENT_ID, sort="recorded_at_asc", limit=2, store=store)
    assert len(limited) == 2
