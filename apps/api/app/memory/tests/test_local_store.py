"""Behaviour tests for the offline LocalStore backend (Slice 2)."""

import pytest

from app.memory.store import get_store, reset_store, store
from app.memory.stores.local_store import LocalStore
from app.schemas.memory import MemoryEvent

PID = "p_001"


def _events() -> list[MemoryEvent]:
    """Small fixture set: wallet, Ravi, two blue-pill intakes ~40 min apart, 3 observations."""
    return [
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-07-01T09:00:00Z",
            event_type="object_location",
            transcript="I kept my wallet near the TV.",
            entities={"objects": [{"name": "wallet", "location": "near the TV"}]},
        ),
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-06-28T17:00:00Z",
            event_type="person_mention",
            transcript="Ravi came to see me.",
            entities={"people": [{"name": "Ravi", "relationship": "son"}]},
        ),
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-07-01T08:30:00Z",
            event_type="medication_intake",
            transcript="Took the blue pill after breakfast.",
            entities={"medications": [{"name": "blue pill"}]},
        ),
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-07-01T09:10:00Z",
            event_type="medication_intake",
            transcript="Took the blue pill again.",
            entities={"medications": [{"name": "blue pill"}]},
        ),
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-06-29T20:00:00Z",
            event_type="observation",
            transcript="Confused after dinner.",
        ),
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-06-30T20:00:00Z",
            event_type="observation",
            transcript="Confused after dinner.",
        ),
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-07-01T20:00:00Z",
            event_type="observation",
            transcript="Confused after dinner.",
        ),
    ]


@pytest.fixture()
def local() -> LocalStore:
    s = LocalStore()
    for ev in _events():
        s.add_event(ev)
    return s


# -- add_event ----------------------------------------------------------------


def test_add_event_generates_id():
    s = LocalStore()
    eid = s.add_event(
        MemoryEvent(patient_id=PID, recorded_at="2026-07-01T09:00:00Z", event_type="general")
    )
    assert eid.startswith("evt_")


def test_add_event_honors_provided_id():
    s = LocalStore()
    eid = s.add_event(
        MemoryEvent(
            patient_id=PID,
            event_id="fixed_1",
            recorded_at="2026-07-01T09:00:00Z",
            event_type="general",
        )
    )
    assert eid == "fixed_1"


# -- query --------------------------------------------------------------------


def test_query_wallet(local: LocalStore):
    rows = local.query(PID, "where is my wallet")
    assert rows, "expected at least one result"
    top = rows[0]
    assert top.node_type == "ObjectLocation"
    assert "wallet" in top.fact.lower()
    assert top.source == "voice_note"
    assert top.verification_status == "unverified"
    assert top.note_id


def test_query_person_boost(local: LocalStore):
    rows = local.query(PID, "who is Ravi")
    assert rows
    assert rows[0].node_type == "PersonMention"
    assert "ravi" in rows[0].fact.lower()


def test_query_no_match_is_empty(local: LocalStore):
    assert local.query(PID, "xyzzy quux") == []


def test_appointment_fact_prefers_transcript_when_summary_is_generic():
    s = LocalStore()
    eid = s.add_event(
        MemoryEvent(
            patient_id=PID,
            recorded_at="2026-07-04T09:30:00Z",
            event_type="appointment",
            transcript="I have a dentist appointment next Tuesday at 2 pm.",
            entities={
                "appointments": [
                    {
                        "title": "Appointment",
                        "doctor": None,
                        "datetime": None,
                    }
                ]
            },
        )
    )

    rows = s.list_memories(PID, sort="recorded_at_desc", limit=1)
    assert rows and rows[0].note_id == eid
    assert rows[0].fact == "I have a dentist appointment next Tuesday at 2 pm."


# -- verification -------------------------------------------------------------


def test_set_verification_flow(local: LocalStore):
    eid = local.query(PID, "where is my wallet")[0].note_id
    assert local.set_verification(PID, eid, "confirmed", "nurse_amy") is True

    row = next(r for r in local.query(PID, "where is my wallet") if r.note_id == eid)
    assert row.verification_status == "confirmed"
    assert row.verified_by == "nurse_amy"


def test_set_verification_missing_returns_false(local: LocalStore):
    assert local.set_verification(PID, "nope", "confirmed", "x") is False


# -- recent_intake_events (window semantics) ----------------------------------


def test_recent_intake_events_within_window(local: LocalStore):
    rows = local.recent_intake_events(PID, "blue pill", 180)
    assert len(rows) == 2
    assert all(r.node_type == "MedicationIntake" for r in rows)
    # latest first
    assert rows[0].recorded_at == "2026-07-01T09:10:00Z"


def test_recent_intake_events_tight_window(local: LocalStore):
    # the two intakes are 40 min apart; a 10-min window keeps only the most recent
    rows = local.recent_intake_events(PID, "blue pill", 10)
    assert len(rows) == 1
    assert rows[0].recorded_at == "2026-07-01T09:10:00Z"


# -- consolidate --------------------------------------------------------------


def test_consolidate_surfaces_repeated_observation(local: LocalStore):
    out = local.consolidate(PID)
    assert "run_id" in out
    patterns = out["patterns"]
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern["count"] == 3
    assert len(pattern["related_note_ids"]) == 3
    assert "confused after dinner" in pattern["pattern"].lower()


# -- forget -------------------------------------------------------------------


def test_forget_single_event(local: LocalStore):
    eid = local.query(PID, "where is my wallet")[0].note_id
    assert local.forget(PID, eid) is True
    assert local.query(PID, "where is my wallet") == []
    assert local.forget(PID, eid) is False  # already gone


def test_forget_whole_patient(local: LocalStore):
    assert local.forget(PID) is True
    assert local.query(PID, "wallet") == []
    assert local.consolidate(PID)["patterns"] == []


# -- graph --------------------------------------------------------------------


def test_graph_is_typed_and_labelled(local: LocalStore):
    g = local.graph(PID)
    nodes, edges = g["nodes"], g["edges"]
    types = {n["type"] for n in nodes}
    assert "Patient" in types
    assert {"ObjectLocation", "PersonMention", "MedicationIntake"} <= types
    # entity nodes exist too, so it's not one blob per note
    assert {"Medication", "Person", "ObjectItem", "Place"} <= types
    assert len(nodes) > 7  # 7 events + patient + entity nodes
    assert all("label" in e for e in edges)
    assert any(e["label"] == "RECORDED" for e in edges)
    assert any(e["label"] == "LOCATED_AT" for e in edges)


# -- factory / singleton ------------------------------------------------------


def test_default_backend_is_local(monkeypatch):
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    reset_store()
    assert get_store().backend_name == "local"
    assert store() is store()  # singleton
    reset_store()
