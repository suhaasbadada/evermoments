"""CogneeBlobStore: placeholder for the deferred ``blob`` MemoryStore backend.

Selected by ``MEMORY_BACKEND=blob`` (see ``store.get_store()``). The blob backend is
planned — a cognee-backed store that keeps the raw memory blob alongside the graph — but is
not built yet. This stub exists so selecting the backend imports cleanly and every operation
fails LOUD with ``NotImplementedError`` rather than an ``ImportError`` on a missing module or,
worse, a silent/misleading result.

It intentionally does NOT import ``cognee``: the import stays cheap and the process boots on
``blob`` without pulling the heavy dependency, matching the resilience-seam design in
``store.py``. Fill these methods in when the blob backend is implemented (Slice 9+).
"""

from app.memory.store import MemoryStore
from app.schemas.memory import ListFilters, MemoryEvent, MemoryResult, VerificationStatus

_NOT_IMPLEMENTED = "blob backend is not implemented yet (set MEMORY_BACKEND=local or =graph)"


class CogneeBlobStore(MemoryStore):
    backend_name = "blob"

    def add_event(self, event: MemoryEvent) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def query(self, patient_id: str, query_text: str, top_k: int = 5) -> list[MemoryResult]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_memories(
        self,
        patient_id: str,
        filters: ListFilters | None = None,
        sort: str = "recorded_at_desc",
        limit: int | None = None,
    ) -> list[MemoryResult]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def recent_intake_events(
        self, patient_id: str, medication_name: str, within_minutes: int
    ) -> list[MemoryResult]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def set_verification(
        self, patient_id: str, event_id: str, status: VerificationStatus, by: str | None
    ) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def consolidate(self, patient_id: str) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def forget(self, patient_id: str, event_id: str | None = None) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def graph(self, patient_id: str) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED)
