"""HTTP surface for the Cognee Memory Engine (Module 3), mounted at ``/api/memory``.

Every handler delegates to the engine (``app.memory.engine``) and talks only in the
boundary contract types (``MemoryEvent`` in, ``MemoryAnswer`` out) — the two exceptions
are ``GET /health`` (reads the active backend name) and ``POST /seed`` (loads the p_001
demo dataset). Handlers use the process-wide singleton store, so ingested data survives
across requests.

Request bodies live in ``app.schemas.memory``; the endpoint-specific *response* shapes
are defined here to keep ``schemas/memory.py`` focused on the module boundary contract.

FROZEN HTTP contract (do not change paths without team sign-off):
    GET  /api/memory/health
    POST /api/memory/events
    POST /api/memory/query
    POST /api/memory/verify
    POST /api/memory/consolidate
    POST /api/memory/forget
    GET  /api/memory/graph/{patient_id}
    POST /api/memory/seed
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.memory import engine, seed
from app.memory.store import store
from app.schemas.memory import (
    ConsolidateRequest,
    ForgetRequest,
    MemoryAnswer,
    MemoryEvent,
    MemoryWarning,
    QueryRequest,
    VerifyRequest,
)

router = APIRouter()


# --- endpoint-specific response models ---------------------------------------


class HealthResponse(BaseModel):
    backend: str
    status: str = "ok"


class IngestResponse(BaseModel):
    event_id: str
    status: str
    warning: MemoryWarning | None = None


class VerifyResponse(BaseModel):
    updated: bool


class ConsolidateResponse(BaseModel):
    run_id: str
    patterns: list[dict] = Field(default_factory=list)


class ForgetResponse(BaseModel):
    forgot: bool


class GraphResponse(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class SeedRequest(BaseModel):
    patient_id: str = seed.PATIENT_ID


class SeedResponse(BaseModel):
    patient_id: str
    loaded: int


# --- routes ------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report which MemoryStore backend is live (local | graph | blob)."""
    return HealthResponse(backend=store().backend_name)


@router.post("/events", response_model=IngestResponse)
def ingest_event(event: MemoryEvent) -> IngestResponse:
    """Persist a memory event; runs the double-dose safety check for medication intakes."""
    result = engine.ingest_memory_event(event)
    return IngestResponse(**result)


@router.post("/query", response_model=MemoryAnswer)
def query(req: QueryRequest) -> MemoryAnswer:
    """Answer a memory question with provenance and calm, source-aware phrasing."""
    return engine.query_memory(req.patient_id, req.query, req.top_k)


@router.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest) -> VerifyResponse:
    """Set a caregiver verification on an event. 404 if the event is not found."""
    updated = engine.verify_memory(req.patient_id, req.event_id, req.status, req.by)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No event {req.event_id!r} for patient {req.patient_id!r}",
        )
    return VerifyResponse(updated=True)


@router.post("/consolidate", response_model=ConsolidateResponse)
def consolidate(req: ConsolidateRequest) -> ConsolidateResponse:
    """Surface repeated patterns from a patient's memories."""
    return ConsolidateResponse(**engine.consolidate(req.patient_id))


@router.post("/forget", response_model=ForgetResponse)
def forget(req: ForgetRequest) -> ForgetResponse:
    """Delete one event, or the patient's whole memory set. Idempotent (200 either way)."""
    return ForgetResponse(forgot=engine.forget_memory(req.patient_id, req.event_id))


@router.get("/graph/{patient_id}", response_model=GraphResponse)
def graph(patient_id: str) -> GraphResponse:
    """Export the patient's memory as typed nodes + labelled edges."""
    return GraphResponse(**engine.graph(patient_id))


@router.post("/seed", response_model=SeedResponse)
def seed_patient(req: SeedRequest | None = None) -> SeedResponse:
    """Load the p_001 demo dataset into the active backend (idempotent).

    The seed dataset is defined only for the demo patient (``p_001``); any other
    ``patient_id`` is rejected rather than silently seeding the wrong id.
    """
    patient_id = req.patient_id if req else seed.PATIENT_ID
    if patient_id != seed.PATIENT_ID:
        raise HTTPException(
            status_code=400,
            detail=f"seed dataset is only defined for {seed.PATIENT_ID!r}",
        )
    target = store()
    seed.load_baseline(target)
    return SeedResponse(patient_id=patient_id, loaded=len(seed.baseline_events()))
