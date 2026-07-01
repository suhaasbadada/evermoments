"""The MemoryStore interface + backend factory (the resilience seam).

The engine and API talk ONLY to the ``MemoryStore`` abstract interface — never a
concrete backend. The active backend is chosen at runtime from ``MEMORY_BACKEND``
(``local`` | ``graph`` | ``blob``, default ``local``). Backends are lazily imported
so selecting ``local`` never pulls in ``cognee`` (guardrail #1) and so this module
has no import cycle with the concrete stores.
"""

import logging
import os
from abc import ABC, abstractmethod

from app.schemas.memory import MemoryEvent, MemoryResult, VerificationStatus

logger = logging.getLogger(__name__)

# The store interface's "ResultRow" is the contract's MemoryResult — one shape,
# one source of truth. Alias kept for readability against the brief's wording.
ResultRow = MemoryResult

VALID_BACKENDS = ("local", "graph", "blob")


class MemoryStore(ABC):
    """Abstract memory backend. All backends behave identically on the contract,
    provenance, and contradiction surfaces; only the storage/recall internals differ."""

    #: "local" | "graph" | "blob" — surfaced by GET /api/memory/health.
    backend_name: str = "abstract"

    @abstractmethod
    def add_event(self, event: MemoryEvent) -> str:
        """Persist an event and return its event_id (generated if absent)."""

    @abstractmethod
    def query(self, patient_id: str, query_text: str, top_k: int = 5) -> list[MemoryResult]:
        """Return up to ``top_k`` relevant facts with full provenance (may be empty)."""

    @abstractmethod
    def recent_intake_events(
        self, patient_id: str, medication_name: str, within_minutes: int
    ) -> list[MemoryResult]:
        """Return recent medication_intake rows for one medication, latest first.

        "Recent" means within ``within_minutes`` of the most-recent matching intake
        (stored timestamps only — never wall-clock), so contradiction detection is
        deterministic and identical across backends (guardrail #5)."""

    @abstractmethod
    def set_verification(
        self, patient_id: str, event_id: str, status: VerificationStatus, by: str | None
    ) -> bool:
        """Update an event's caregiver verification. Return False if not found."""

    @abstractmethod
    def consolidate(self, patient_id: str) -> dict:
        """Surface derived patterns from repeated memories. Returns {run_id, patterns}."""

    @abstractmethod
    def forget(self, patient_id: str, event_id: str | None = None) -> bool:
        """Delete one event, or the patient's whole memory set. Return whether anything was removed."""

    @abstractmethod
    def graph(self, patient_id: str) -> dict:
        """Export the patient's memory as typed nodes + labelled edges: {nodes, edges}."""


def get_store() -> MemoryStore:
    """Construct a fresh store for the backend named by ``MEMORY_BACKEND``.

    Lazy imports keep ``cognee`` out of the ``local`` path and avoid an import cycle.
    An unknown value falls back to ``local`` (resilience-first) with a warning.
    """
    backend = os.getenv("MEMORY_BACKEND", "local").strip().lower()

    if backend == "local":
        from app.memory.stores.local_store import LocalStore

        logger.info("MEMORY_BACKEND=local -> LocalStore (offline, in-memory)")
        return LocalStore()
    if backend == "graph":
        from app.memory.stores.graph_store import CogneeGraphStore

        logger.info("MEMORY_BACKEND=graph -> CogneeGraphStore")
        return CogneeGraphStore()
    if backend == "blob":
        from app.memory.stores.blob_store import CogneeBlobStore

        logger.info("MEMORY_BACKEND=blob -> CogneeBlobStore")
        return CogneeBlobStore()

    logger.warning("Unknown MEMORY_BACKEND=%r; falling back to local", backend)
    from app.memory.stores.local_store import LocalStore

    return LocalStore()


_store: MemoryStore | None = None


def store() -> MemoryStore:
    """Process-wide singleton store, so in-memory data survives across API requests."""
    global _store
    if _store is None:
        _store = get_store()
    return _store


def reset_store() -> None:
    """Drop the singleton so the next ``store()`` rebuilds from the current env (tests)."""
    global _store
    _store = None
