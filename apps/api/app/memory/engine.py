"""The memory engine — the module the API calls.

Orchestrates ingest / query / verify / consolidate / forget / graph while talking
ONLY to the ``MemoryStore`` interface (guardrail #3). It owns event-id generation,
the calm patient-facing phrasing, and running the double-dose check on ingest.
The active backend is injected (defaults to the process singleton), so the API
uses the shared store and tests can pass a fresh LocalStore.
"""

from uuid import uuid4

from app.memory.contradiction import check_double_dose
from app.memory.store import MemoryStore
from app.memory.store import store as current_store
from app.schemas.memory import (
    MemoryAnswer,
    MemoryEvent,
    MemoryResult,
    VerificationStatus,
)

EMPTY_RECALL_MESSAGE = (
    "I don't have a memory about that yet. "
    "You could check with a caregiver, or record a new note."
)


def _new_event_id() -> str:
    return f"evt_{uuid4().hex[:12]}"


def _status_clause(status: str, verified_by: str | None) -> str:
    if status == "confirmed":
        return (
            f"A caregiver ({verified_by}) has confirmed this."
            if verified_by
            else "A caregiver has confirmed this."
        )
    if status == "needs_check":
        return "A caregiver has asked to double-check this."
    if status == "incorrect":
        return "A caregiver marked this as not correct."
    if status == "safety_critical":
        return "A caregiver flagged this as important for safety."
    # default / unverified
    return "This hasn't been confirmed by a caregiver yet."


def _answer_text(rows: list[MemoryResult]) -> str:
    """A calm, patient-friendly answer that reflects caregiver status. Deterministic."""
    if not rows:
        return EMPTY_RECALL_MESSAGE

    top = rows[0]
    lead = top.fact.strip()
    if lead:
        lead = lead[0].upper() + lead[1:]
        if not lead.endswith((".", "!", "?")):
            lead += "."

    clause = _status_clause(top.verification_status, top.verified_by)

    extra = ""
    others = len(rows) - 1
    if others > 0:
        extra = f" I also found {others} other related note{'s' if others > 1 else ''}."

    return f"{lead} {clause}{extra}".strip()


def ingest_memory_event(event: MemoryEvent, store: MemoryStore | None = None) -> dict:
    """Persist an event and run the double-dose safety check. Returns {event_id, status, warning}."""
    s = store or current_store()
    eid = event.event_id or _new_event_id()
    stored_event = event if event.event_id else event.model_copy(update={"event_id": eid})

    s.add_event(stored_event)
    warning = check_double_dose(s, stored_event)  # no-op for non-medication events

    return {"event_id": eid, "status": "stored", "warning": warning}


def query_memory(
    patient_id: str, query: str, top_k: int = 5, store: MemoryStore | None = None
) -> MemoryAnswer:
    """Answer a memory question with full provenance and a calm, source-aware phrasing."""
    s = store or current_store()
    rows = s.query(patient_id, query, top_k)
    return MemoryAnswer(
        query=query,
        answer=_answer_text(rows),
        results=rows,
        warnings=[],
    )


def verify_memory(
    patient_id: str,
    event_id: str,
    status: VerificationStatus,
    by: str | None = None,
    store: MemoryStore | None = None,
) -> bool:
    """Set a caregiver verification on an event."""
    s = store or current_store()
    return s.set_verification(patient_id, event_id, status, by)


def consolidate(patient_id: str, store: MemoryStore | None = None) -> dict:
    """Consolidate repeated memories into derived patterns. Returns {run_id, patterns}."""
    s = store or current_store()
    return s.consolidate(patient_id)


def forget_memory(
    patient_id: str, event_id: str | None = None, store: MemoryStore | None = None
) -> bool:
    """Delete one event, or the patient's whole memory set."""
    s = store or current_store()
    return s.forget(patient_id, event_id)


def graph(patient_id: str, store: MemoryStore | None = None) -> dict:
    """Export the patient's memory as typed nodes + labelled edges: {nodes, edges}."""
    s = store or current_store()
    return s.graph(patient_id)
