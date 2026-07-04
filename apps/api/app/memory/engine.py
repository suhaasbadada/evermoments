"""The memory engine — the module the API calls.

Orchestrates ingest / query / verify / consolidate / forget / graph while talking
ONLY to the ``MemoryStore`` interface (guardrail #3). It owns event-id generation,
the calm patient-facing phrasing, and running the double-dose check on ingest.
The active backend is injected (defaults to the process singleton), so the API
uses the shared store and tests can pass a fresh LocalStore.
"""

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.memory.contradiction import check_double_dose
from app.memory.store import MemoryStore
from app.memory.store import store as current_store
from app.services.llm_answer import synthesize_answer_with_groq
from app.schemas.memory import (
    ListFilters,
    MemoryAnswer,
    MemoryEvent,
    MemoryResult,
    VerificationStatus,
)

EMPTY_RECALL_MESSAGE = (
    "I don't have a memory about that yet. "
    "You could check with a caregiver, or record a new note."
)

# --- Temporal / enumeration question routing (Fix 2) ------------------------
# Questions like "what did I record today" are enumerations over a time window, not content
# lookups — semantic query() dead-ends on them when the words don't appear in any note. We
# detect them deterministically at the top of query_memory() and answer via list_memories()
# with a computed date range instead. CONSERVATIVE: reroute ONLY when BOTH an enumeration cue
# AND a resolvable temporal term are present, so factual/relational/ambiguous questions stay on
# the normal path (which keeps the graph hybrid). Pure Python (no cognee) — Tier 1 tests it.
#
# Timezone: "today" is a UTC calendar day. recorded_at is stored in UTC (…Z) and _parse_ts
# treats naive as UTC, so UTC day bounds are consistent with the data. Bounds are INCLUSIVE
# (filter_sort_limit compares >= date_from and <= date_to).

# Enumeration intent — the act of recalling recorded notes, not a specific content noun.
_ENUM_RE = re.compile(
    r"""(?xi)
      \brecord(?:ed|ing)?\b | \blog(?:ged|ging)?\b | \bnotes?\b | \bnoted\b
    | \bmemor(?:y|ies)\b | \beverything\b | \banything\b
    | \bshow\ me\b | \blist\b
    | \bwhat\ did\ i\ (?:say|tell|record|note|log|do)\b
    | \bwhat\ have\ i\ (?:recorded|said|noted|logged|done)\b
    """
)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_VISITOR_RE = re.compile(r"\b(who\s+visited|visitor|came\s+over)\b", re.I)
_ACTIVITY_RE = re.compile(r"\bwhat\s+(did|have)\s+i\s+(do|done)\b", re.I)
_EATING_RE = re.compile(r"\b(eat|eating|ate|dinner|lunch|breakfast|meal|pizza|food)\b", re.I)
_FOOD_HINT_RE = re.compile(
    r"\b(pizza|food|meal|dinner|lunch|breakfast|snack|eat|ate|drank|drink|restaurant|cafe)\b",
    re.I,
)
_MEDICATION_QUERY_RE = re.compile(
    r"\b(medications?|medicines?|meds?|pills?|tablets?|capsules?|doses?)\b", re.I
)
_MEDICATION_ACTION_RE = re.compile(
    r"\b(take|took|taken|taking|did\s+i\s+take|have\s+i\s+taken|have\s+i\s+had)\b",
    re.I,
)
_KINSHIP_RELATIONS = (
    "son",
    "daughter",
    "mother",
    "father",
    "mom",
    "dad",
    "brother",
    "sister",
    "husband",
    "wife",
)
_KINSHIP_Q_RE = re.compile(
    r"\bwho\s+is\s+my\s+(son|daughter|mother|father|mom|dad|brother|sister|husband|wife)\b",
    re.I,
)


def _day_bounds(day: datetime) -> tuple[str, str]:
    """Inclusive UTC start/end-of-day ISO strings for the calendar day of ``day``."""
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start.isoformat(), end.isoformat()


def _temporal_filters(query: str, now: datetime) -> tuple[ListFilters, str] | None:
    """Classify a question as temporal-enumeration and return (ListFilters, label), else None.

    Pure & deterministic given ``now`` (a tz-aware UTC datetime). Returns None — leaving the
    question on the normal semantic/graph path — unless BOTH an enumeration cue and a resolvable
    temporal term are found. ``label`` is a phrase for the answer text (e.g. "today")."""
    q = (query or "").strip()
    if not q or not _ENUM_RE.search(q):
        return None
    ql = q.lower()

    # Explicit ISO date(s) first: two → inclusive range, one → that single day.
    iso = _ISO_DATE_RE.findall(q)
    if len(iso) >= 2:
        lo, _ = _day_bounds(_iso_to_utc(iso[0]))
        _, hi = _day_bounds(_iso_to_utc(iso[1]))
        return ListFilters(date_from=lo, date_to=hi), f"between {iso[0]} and {iso[1]}"
    if len(iso) == 1:
        lo, hi = _day_bounds(_iso_to_utc(iso[0]))
        return ListFilters(date_from=lo, date_to=hi), f"on {iso[0]}"

    # Relative terms (order matters: "yesterday" before "today").
    if "yesterday" in ql:
        lo, hi = _day_bounds(now - timedelta(days=1))
        return ListFilters(date_from=lo, date_to=hi), "yesterday"
    if "today" in ql:  # also matches "today's"
        lo, hi = _day_bounds(now)
        return ListFilters(date_from=lo, date_to=hi), "today"
    if "this week" in ql:
        monday = now - timedelta(days=now.weekday())  # Monday-based calendar week
        lo, _ = _day_bounds(monday)
        _, hi = _day_bounds(now)
        return ListFilters(date_from=lo, date_to=hi), "this week"
    if "this month" in ql:
        lo, _ = _day_bounds(now.replace(day=1))
        _, hi = _day_bounds(now)
        return ListFilters(date_from=lo, date_to=hi), "this month"
    return None


def _iso_to_utc(d: str) -> datetime:
    """A bare YYYY-MM-DD -> tz-aware UTC midnight datetime for day-bounds math."""
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


def _temporal_answer_text(label: str, rows: list[MemoryResult]) -> str:
    """Calm natural-language lead for a temporal enumeration (never a dead-end)."""
    if not rows:
        return (
            f"I don't have any memories recorded {label}. "
            "You could record a new note, or check with a caregiver."
        )
    # Strip each fact's trailing sentence punctuation so the joined list reads cleanly
    # (avoids "evening.." when a transcript already ends in a period).
    facts = "; ".join(r.fact.strip().rstrip(".;") for r in rows if r.fact.strip())
    return f"Here's what you recorded {label}: {facts}."


def _intent_fallback_rows(
    patient_id: str,
    query: str,
    top_k: int,
    s: MemoryStore,
) -> list[MemoryResult]:
    """Deterministic fallback for broad natural-language prompts when token recall is empty."""
    q = (query or "").strip().lower()
    if not q:
        return []

    if _VISITOR_RE.search(q):
        return s.list_memories(
            patient_id,
            ListFilters(event_type="person_mention"),
            sort="recorded_at_desc",
            limit=top_k,
        )

    if _KINSHIP_Q_RE.search(q):
        return s.list_memories(
            patient_id,
            ListFilters(event_type="person_mention"),
            sort="recorded_at_desc",
            limit=top_k,
        )

    if _EATING_RE.search(q):
        recent = s.list_memories(patient_id, sort="recorded_at_desc", limit=50)
        hinted = [row for row in recent if _FOOD_HINT_RE.search(row.fact)]
        return hinted[:top_k]

    if _ACTIVITY_RE.search(q):
        return s.list_memories(patient_id, sort="recorded_at_desc", limit=top_k)

    return []


def _medication_check_route(
    patient_id: str,
    query: str,
    top_k: int,
    s: MemoryStore,
    now: datetime,
) -> tuple[list[MemoryResult], str | None] | None:
    """Route medication check questions to event_type-filtered list lookups.

    This avoids lexical false positives where a temporal term like "today" matches
    unrelated notes better than actual medication memories.
    """
    q = (query or "").strip()
    if not q:
        return None
    if not _MEDICATION_QUERY_RE.search(q):
        return None
    if not (_MEDICATION_ACTION_RE.search(q) or "did i" in q.lower()):
        return None

    filters = ListFilters(event_type="medication_intake")
    label: str | None = None
    ql = q.lower()

    iso = _ISO_DATE_RE.findall(q)
    if len(iso) >= 1:
        lo, hi = _day_bounds(_iso_to_utc(iso[0]))
        filters.date_from = lo
        filters.date_to = hi
        label = f"on {iso[0]}"
    elif "yesterday" in ql:
        lo, hi = _day_bounds(now - timedelta(days=1))
        filters.date_from = lo
        filters.date_to = hi
        label = "yesterday"
    elif "today" in ql:
        lo, hi = _day_bounds(now)
        filters.date_from = lo
        filters.date_to = hi
        label = "today"

    rows = s.list_memories(patient_id, filters, sort="recorded_at_desc", limit=top_k)
    return rows, label


def _medication_check_answer(rows: list[MemoryResult], label: str | None) -> str:
    if not rows:
        window = f" {label}" if label else ""
        return (
            f"I don't have a memory of taking medicine{window} yet. "
            "If this seems wrong, please record it again or ask a caregiver to verify."
        )

    top = rows[0]
    lead = top.fact.strip()
    if lead:
        lead = lead[0].upper() + lead[1:]
        if not lead.endswith((".", "!", "?")):
            lead += "."

    scope = f" {label}" if label else ""
    clause = _status_clause(top.verification_status, top.verified_by)
    extra = ""
    others = len(rows) - 1
    if others > 0:
        extra = f" I also found {others} other related note{'s' if others > 1 else ''}."
    return f"Based on your notes{scope}, yes: {lead} {clause}{extra}".strip()


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


def _kinship_answer(query: str, rows: list[MemoryResult]) -> str | None:
    """Return a relation-specific answer for questions like "Who is my son?"."""
    if not rows:
        return None

    match = _KINSHIP_Q_RE.search((query or "").strip())
    if not match:
        return None

    relation = match.group(1).lower()
    relation_word = relation
    if relation == "mom":
        relation_word = "mother"
    elif relation == "dad":
        relation_word = "father"

    # Prefer names explicitly tied to the asked relation in recalled facts.
    for row in rows:
        fact = (row.fact or "").strip()
        if not fact:
            continue

        # Match variants like:
        # "My son Ravi came to visit" or "Ravi - son" / "Ravi — son".
        patterns = [
            re.compile(
                rf"\bmy\s+{re.escape(relation)}\s+([A-Za-z][A-Za-z'\-]*)\b",
                re.I,
            ),
            re.compile(
                rf"\b([A-Za-z][A-Za-z'\-]*)\s*[\-\u2014]\s*{re.escape(relation)}\b",
                re.I,
            ),
        ]

        for pattern in patterns:
            name_match = pattern.search(fact)
            if not name_match:
                continue
            name = name_match.group(1).strip(" .,!?:;")
            if not name:
                continue

            name = " ".join(part.capitalize() for part in name.split())
            clause = _status_clause(row.verification_status, row.verified_by)
            return f"{name} is your {relation_word}. {clause}"

    return None


def _maybe_llm_answer(query: str, rows: list[MemoryResult]) -> str | None:
    """Best-effort Groq synthesis; deterministic answer remains the fallback."""
    return synthesize_answer_with_groq(query, rows)


def ingest_memory_event(event: MemoryEvent, store: MemoryStore | None = None) -> dict:
    """Persist an event and run the double-dose safety check. Returns {event_id, status, warning}."""
    s = store or current_store()
    eid = event.event_id or _new_event_id()
    stored_event = event if event.event_id else event.model_copy(update={"event_id": eid})

    s.add_event(stored_event)
    warning = check_double_dose(s, stored_event)  # no-op for non-medication events

    return {"event_id": eid, "status": "stored", "warning": warning}


def query_memory(
    patient_id: str,
    query: str,
    top_k: int = 5,
    store: MemoryStore | None = None,
    now: datetime | None = None,
) -> MemoryAnswer:
    """Answer a memory question with full provenance and a calm, source-aware phrasing.

    Temporal-enumeration questions ("what did I record today") are routed to list_memories over
    a computed date range so they don't dead-end on semantic matching; everything else goes to
    the store's query() (which keeps the relational/factual graph hybrid). ``now`` is injectable
    for deterministic tests; it defaults to the current UTC time. Same MemoryAnswer shape either
    way, so clients need no changes."""
    s = store or current_store()

    current_now = now or datetime.now(timezone.utc)

    route = _temporal_filters(query, current_now)
    if route is not None:
        filters, label = route
        rows = s.list_memories(patient_id, filters, sort="recorded_at_asc")
        return MemoryAnswer(
            query=query,
            answer=_temporal_answer_text(label, rows),
            results=rows,
            warnings=[],
        )

    medication_route = _medication_check_route(patient_id, query, top_k, s, current_now)
    if medication_route is not None:
        rows, label = medication_route
        return MemoryAnswer(
            query=query,
            answer=_medication_check_answer(rows, label),
            results=rows,
            warnings=[],
        )

    rows = s.query(patient_id, query, top_k)
    if not rows:
        rows = _intent_fallback_rows(patient_id, query, top_k, s)
    kinship = _kinship_answer(query, rows)
    if kinship is not None:
        return MemoryAnswer(
            query=query,
            answer=kinship,
            results=rows,
            warnings=[],
        )
    llm_answer = _maybe_llm_answer(query, rows)
    if llm_answer is not None:
        return MemoryAnswer(
            query=query,
            answer=llm_answer,
            results=rows,
            warnings=[],
        )
    return MemoryAnswer(
        query=query,
        answer=_answer_text(rows),
        results=rows,
        warnings=[],
    )


def list_memories(
    patient_id: str,
    filters: ListFilters | None = None,
    sort: str = "recorded_at_desc",
    limit: int | None = None,
    store: MemoryStore | None = None,
) -> list[MemoryResult]:
    """Enumerate a patient's memories with optional filters + sort + limit (dashboard views)."""
    s = store or current_store()
    return s.list_memories(patient_id, filters, sort, limit)


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
