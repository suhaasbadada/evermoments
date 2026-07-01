"""Contract test for the Cognee Memory Engine boundary (Slice 1).

Two jobs:
1. A "drift alarm" — exact field-name sets are pinned, so renaming or dropping a
   contract field fails here (guardrail #2: update the contract and its tests together).
2. Behavioural checks — defaults, nested parsing, required fields, Literal validation,
   the ISO-8601 recorded_at validator, round-trip, and the outbound answer shape.
"""

import pytest
from pydantic import ValidationError

from app.schemas.memory import (
    Appointment,
    ConsolidateRequest,
    Entities,
    ForgetRequest,
    Medication,
    MemoryAnswer,
    MemoryEvent,
    MemoryResult,
    MemoryWarning,
    ObjectItem,
    Person,
    Place,
    QueryRequest,
    Verification,
    VerifyRequest,
)


def _wallet_event() -> dict:
    """A minimal valid object_location event (the demo's wallet note)."""
    return {
        "patient_id": "p_001",
        "recorded_at": "2026-07-01T09:00:00Z",
        "event_type": "object_location",
        "transcript": "I kept my wallet near the TV.",
        "entities": {"objects": [{"name": "wallet", "location": "near the TV"}]},
    }


# --- 1. Drift alarm: exact field-name sets -----------------------------------


def test_field_names_are_pinned():
    assert set(MemoryEvent.model_fields) == {
        "patient_id",
        "event_id",
        "source",
        "recorded_at",
        "transcript",
        "event_type",
        "entities",
        "verification",
    }
    assert set(MemoryAnswer.model_fields) == {"query", "answer", "results", "warnings"}
    assert set(MemoryResult.model_fields) == {
        "fact",
        "node_type",
        "recorded_at",
        "source",
        "verification_status",
        "verified_by",
        "note_id",
    }
    assert set(MemoryWarning.model_fields) == {"type", "message", "related_note_ids"}
    assert set(Entities.model_fields) == {
        "medications",
        "people",
        "places",
        "objects",
        "appointments",
        "time_reference",
    }
    assert set(Verification.model_fields) == {"status", "by", "at"}
    assert set(Medication.model_fields) == {"name", "form"}
    assert set(Person.model_fields) == {"name", "relationship"}
    assert set(Place.model_fields) == {"name"}
    assert set(ObjectItem.model_fields) == {"name", "location"}
    assert set(Appointment.model_fields) == {"title", "datetime", "doctor"}
    assert set(QueryRequest.model_fields) == {"patient_id", "query", "top_k"}
    assert set(VerifyRequest.model_fields) == {"patient_id", "event_id", "status", "by"}
    assert set(ConsolidateRequest.model_fields) == {"patient_id"}
    assert set(ForgetRequest.model_fields) == {"patient_id", "event_id"}


# --- 2. Defaults & nested parsing --------------------------------------------


def test_defaults_applied():
    event = MemoryEvent(**_wallet_event())
    assert event.source == "voice_note"
    assert event.event_id is None
    assert event.verification.status == "unverified"
    assert event.verification.by is None
    assert event.entities.medications == []
    assert event.entities.people == []
    assert event.entities.time_reference is None
    # the one entity we did pass parsed into a typed model
    assert event.entities.objects[0] == ObjectItem(name="wallet", location="near the TV")


def test_nested_medication_parsing():
    event = MemoryEvent(
        patient_id="p_001",
        recorded_at="2026-07-01T08:30:00Z",
        event_type="medication_intake",
        entities={"medications": [{"name": "blue pill"}]},
    )
    med = event.entities.medications[0]
    assert isinstance(med, Medication)
    assert med.name == "blue pill"
    assert med.form is None


# --- 3. Required fields -------------------------------------------------------


@pytest.mark.parametrize("missing", ["patient_id", "recorded_at", "event_type"])
def test_required_fields_enforced(missing):
    data = {
        "patient_id": "p_001",
        "recorded_at": "2026-07-01T09:00:00Z",
        "event_type": "general",
    }
    del data[missing]
    with pytest.raises(ValidationError):
        MemoryEvent(**data)


# --- 4. Literal validation ----------------------------------------------------


def test_invalid_source_rejected():
    data = _wallet_event()
    data["source"] = "telepathy"
    with pytest.raises(ValidationError):
        MemoryEvent(**data)


def test_invalid_event_type_rejected():
    data = _wallet_event()
    data["event_type"] = "not_a_type"
    with pytest.raises(ValidationError):
        MemoryEvent(**data)


def test_invalid_verification_status_rejected():
    data = _wallet_event()
    data["verification"] = {"status": "bogus"}
    with pytest.raises(ValidationError):
        MemoryEvent(**data)


# --- 5. ISO-8601 recorded_at validator ---------------------------------------


def test_recorded_at_must_be_iso():
    data = _wallet_event()
    data["recorded_at"] = "not-a-date"
    with pytest.raises(ValidationError):
        MemoryEvent(**data)


@pytest.mark.parametrize(
    "ts",
    ["2026-07-01T09:00:00Z", "2026-07-01T09:00:00+05:30", "2026-07-01T09:00:00"],
)
def test_recorded_at_accepts_valid_iso(ts):
    event = MemoryEvent(patient_id="p_001", recorded_at=ts, event_type="general")
    assert event.recorded_at == ts  # original string preserved


# --- 6. Round-trip ------------------------------------------------------------


def test_round_trip_dump_reload():
    original = MemoryEvent(**_wallet_event())
    reloaded = MemoryEvent(**original.model_dump())
    assert reloaded == original


# --- 7. Outbound answer shape -------------------------------------------------


def test_memory_answer_shape():
    answer = MemoryAnswer(
        query="where is my wallet",
        answer="Your wallet is near the TV.",
        results=[
            MemoryResult(
                fact="wallet is near the TV",
                node_type="ObjectLocation",
                recorded_at="2026-07-01T09:00:00Z",
                source="voice_note",
                verification_status="unverified",
                verified_by=None,
                note_id="evt_1",
            )
        ],
        warnings=[
            MemoryWarning(
                type="possible_double_dose",
                message="Two intakes close together.",
                related_note_ids=["evt_1", "evt_2"],
            )
        ],
    )
    assert answer.results[0].note_id == "evt_1"
    assert answer.results[0].verification_status == "unverified"
    assert answer.warnings[0].type == "possible_double_dose"
    assert answer.warnings[0].related_note_ids == ["evt_1", "evt_2"]


def test_empty_answer_has_empty_collections():
    answer = MemoryAnswer(query="q", answer="a")
    assert answer.results == []
    assert answer.warnings == []


# --- 8. Request-body defaults -------------------------------------------------


def test_query_request_default_top_k():
    assert QueryRequest(patient_id="p_001", query="where is my wallet").top_k == 5


def test_forget_request_event_id_optional():
    assert ForgetRequest(patient_id="p_001").event_id is None
