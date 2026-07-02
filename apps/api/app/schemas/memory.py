"""Boundary contract for the Cognee Memory Engine (Module 3).

These are the ONLY data shapes allowed to cross the module boundary:
``MemoryEvent`` goes in, ``MemoryAnswer`` comes out. Every backend, the engine,
the API layer, and the seed talk in terms of these models. Do not rename or drop
a field here without updating ``app/memory/tests/test_memory.py`` in the same commit.
"""

from datetime import datetime as _dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --- Shared, validated string types -----------------------------------------

SourceType = Literal["voice_note", "caregiver_note", "document", "manual"]
EventType = Literal[
    "medication_intake",
    "object_location",
    "person_mention",
    "appointment",
    "routine",
    "observation",
    "general",
]
VerificationStatus = Literal[
    "unverified",
    "confirmed",
    "incorrect",
    "needs_check",
    "safety_critical",
]


# --- Entity sub-models (everything under MemoryEvent.entities) ---------------


class Medication(BaseModel):
    name: str
    form: str | None = None


class Person(BaseModel):
    name: str
    relationship: str | None = None


class Place(BaseModel):
    name: str


class ObjectItem(BaseModel):
    name: str
    location: str | None = None


class Appointment(BaseModel):
    title: str
    datetime: str | None = None
    doctor: str | None = None


class Entities(BaseModel):
    medications: list[Medication] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)
    places: list[Place] = Field(default_factory=list)
    objects: list[ObjectItem] = Field(default_factory=list)
    appointments: list[Appointment] = Field(default_factory=list)
    time_reference: str | None = None


class Verification(BaseModel):
    status: VerificationStatus = "unverified"
    by: str | None = None
    at: str | None = None


# --- MemoryEvent: the inbound contract ---------------------------------------


class MemoryEvent(BaseModel):
    """A single structured memory event ingested into the engine."""

    patient_id: str
    event_id: str | None = None
    source: SourceType = "voice_note"
    recorded_at: str
    transcript: str | None = None
    event_type: EventType
    entities: Entities = Field(default_factory=Entities)
    verification: Verification = Field(default_factory=Verification)

    @field_validator("recorded_at")
    @classmethod
    def _validate_recorded_at(cls, value: str) -> str:
        """recorded_at must be a parseable ISO-8601 timestamp.

        Downstream double-dose detection (Slice 4) does timestamp math on this
        field, so we fail fast at the boundary rather than deep in the engine.
        Accept a trailing ``Z`` (UTC) by normalising it before parsing.
        """
        try:
            _dt.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"recorded_at must be ISO-8601, got {value!r}") from exc
        return value


# --- MemoryAnswer: the outbound contract -------------------------------------


class MemoryResult(BaseModel):
    """One recalled fact with full provenance.

    This is also the row type returned by the ``MemoryStore`` interface
    (referred to as "ResultRow" in the store methods) — a single source of truth.
    """

    fact: str
    node_type: str
    recorded_at: str
    source: SourceType
    verification_status: VerificationStatus
    verified_by: str | None = None
    note_id: str


class MemoryWarning(BaseModel):
    """A safety warning surfaced alongside an answer (e.g. possible double dose)."""

    type: str
    message: str
    related_note_ids: list[str] = Field(default_factory=list)


class MemoryAnswer(BaseModel):
    """A patient-friendly answer plus the provenance and warnings behind it."""

    query: str
    answer: str
    results: list[MemoryResult] = Field(default_factory=list)
    warnings: list[MemoryWarning] = Field(default_factory=list)


# --- HTTP request bodies (mirrors app/api/memory_routes.py) ------------------


class QueryRequest(BaseModel):
    patient_id: str
    query: str
    top_k: int = 5


class VerifyRequest(BaseModel):
    patient_id: str
    event_id: str
    status: VerificationStatus
    by: str | None = None


class ConsolidateRequest(BaseModel):
    patient_id: str


class ForgetRequest(BaseModel):
    patient_id: str
    event_id: str | None = None


ListSort = Literal["recorded_at_desc", "recorded_at_asc"]


class ListFilters(BaseModel):
    """Optional filters for ``POST /api/memory/list`` (all fields optional; None = no filter)."""

    event_type: EventType | None = None
    verification_status: VerificationStatus | None = None
    date_from: str | None = None  # inclusive lower bound (ISO-8601)
    date_to: str | None = None    # inclusive upper bound (ISO-8601)

    @field_validator("date_from", "date_to")
    @classmethod
    def _validate_iso_bound(cls, value: str | None) -> str | None:
        """Fail fast on a non-ISO date bound (same rule as ``MemoryEvent.recorded_at``)."""
        if value is None:
            return value
        try:
            _dt.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"date bound must be ISO-8601, got {value!r}") from exc
        return value


class ListRequest(BaseModel):
    patient_id: str
    filters: ListFilters | None = None
    sort: ListSort = "recorded_at_desc"
    limit: int | None = Field(default=None, ge=1)
