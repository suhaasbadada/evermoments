"""LocalStore: the OFFLINE MemoryStore backend.

Pure in-memory dict — no network, no ``cognee``. It implements the full
``MemoryStore`` contract with deterministic keyword/entity recall, a people-graph
boost, pattern consolidation, and a typed node/edge graph export, so the entire
module can be built and demoed with no external dependencies or keys.
"""

import re
import threading
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import settings
from app.memory.store import MemoryStore
from app.schemas.memory import ListFilters, MemoryEvent, MemoryResult

# event_type -> typed graph node label
_NODE_TYPE = {
    "medication_intake": "MedicationIntake",
    "object_location": "ObjectLocation",
    "person_mention": "PersonMention",
    "appointment": "Appointment",
    "routine": "Routine",
    "observation": "Observation",
    "general": "Note",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common question words dropped from queries so matching keys on the meaningful terms.
STOPWORDS = {
    "where", "is", "was", "were", "are", "am", "be", "my", "your", "the", "a", "an",
    "who", "what", "when", "did", "do", "does", "i", "to", "of", "in", "on", "at",
    "me", "you", "it", "that", "this", "and", "or", "have", "has", "had", "with",
}

# How strongly a person-name match in the query pulls a related note up the ranking.
PEOPLE_BOOST = 5


def _resolve_persist_path(configured_path: str) -> str:
    """Resolve persistence file path deterministically across launch directories."""
    raw = (configured_path or "").strip()
    if not raw:
        return ""

    path = Path(raw)
    if path.is_absolute():
        return str(path)

    # Resolve relative paths from repo root (not process CWD) so the same env value
    # points to one file whether API is launched from monorepo root or apps/api.
    repo_root = Path(__file__).resolve().parents[5]
    return str((repo_root / path).resolve())


def _norm(value: str) -> str:
    return value.strip().lower()


def _norm_text(value: str) -> str:
    """Normalise free text for grouping: lowercase, punctuation-stripped, single-spaced."""
    return " ".join(_TOKEN_RE.findall(value.lower()))


def _tokenize(text: str | None) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower())) if text else set()


def _parse_ts(value: str) -> datetime:
    """ISO-8601 -> timezone-aware datetime (naive treated as UTC) for safe arithmetic."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fact_for(event: MemoryEvent) -> str:
    """A concise, factual phrasing of an event (the engine adds the calm wrapper later)."""
    e = event.entities
    et = event.event_type
    if et == "object_location" and e.objects:
        o = e.objects[0]
        return f"{o.name} is {o.location}" if o.location else o.name
    if et == "medication_intake" and e.medications:
        m = e.medications[0]
        medication_summary = f"took {m.name} ({m.form})" if m.form else f"took {m.name}"
        if event.transcript:
            transcript = event.transcript.strip()
            # Keep user wording when extraction is too generic (e.g. "medication")
            # or when transcript carries materially more context.
            if _norm(m.name) == "medication":
                return transcript
            if _norm_text(transcript) and len(_norm_text(transcript)) > len(_norm_text(medication_summary)):
                return transcript
        return medication_summary
    if et == "person_mention" and e.people:
        p = e.people[0]
        person_summary = f"{p.name} — {p.relationship}" if p.relationship else p.name
        if event.transcript:
            transcript = event.transcript.strip()
            # Keep richer spoken context (e.g., "Mom visited me today at 4pm")
            # instead of collapsing to only the person name.
            if _norm_text(transcript) and len(_norm_text(transcript)) > len(_norm_text(person_summary)):
                return transcript
        return person_summary
    if et == "appointment" and e.appointments:
        a = e.appointments[0]
        parts = [a.title]
        if a.doctor:
            parts.append(f"with {a.doctor}")
        if a.datetime:
            parts.append(f"at {a.datetime}")
        appointment_summary = " ".join(part for part in parts if part)
        if event.transcript:
            transcript = event.transcript.strip()
            # Keep spoken wording when extraction collapses to generic appointment labels.
            if _norm(a.title) in {"appointment", "doctor appointment", "checkup", "check-up"}:
                return transcript
            if _norm_text(transcript) and len(_norm_text(transcript)) > len(_norm_text(appointment_summary)):
                return transcript
        return appointment_summary or (event.transcript or "appointment")
    if event.transcript:
        return event.transcript
    return et.replace("_", " ")


def _event_tokens(event: MemoryEvent) -> set[str]:
    """All searchable tokens for an event (transcript + typed entity fields)."""
    e = event.entities
    parts: list[str] = [event.transcript or "", event.event_type]
    for m in e.medications:
        parts += [m.name, m.form or ""]
    for p in e.people:
        parts += [p.name, p.relationship or ""]
    for pl in e.places:
        parts.append(pl.name)
    for o in e.objects:
        parts += [o.name, o.location or ""]
    for a in e.appointments:
        parts += [a.title, a.doctor or "", a.datetime or ""]
    if e.time_reference:
        parts.append(e.time_reference)
    return _tokenize(" ".join(parts))


def _person_tokens(event: MemoryEvent) -> set[str]:
    tokens: set[str] = set()
    for p in event.entities.people:
        tokens |= _tokenize(p.name)
    return tokens


def filter_sort_limit(
    events: list[MemoryEvent],
    filters: ListFilters | None = None,
    sort: str = "recorded_at_desc",
    limit: int | None = None,
) -> list[MemoryEvent]:
    """Apply ``list_memories``' filters + sort + limit to events (pure; shared by all backends).

    The single source of truth for ``/list`` semantics, so ``local`` and ``graph`` return the
    same set and order. ``event_type`` / ``verification_status`` are exact matches; ``date_from``
    / ``date_to`` are inclusive bounds compared via ``_parse_ts``; ordering is by ``recorded_at``
    (desc by default, asc when ``sort == "recorded_at_asc"``); ``limit`` caps the result if set.
    """
    out = list(events)
    if filters is not None:
        if filters.event_type is not None:
            out = [e for e in out if e.event_type == filters.event_type]
        if filters.verification_status is not None:
            out = [e for e in out if e.verification.status == filters.verification_status]
        if filters.date_from is not None:
            lo = _parse_ts(filters.date_from)
            out = [e for e in out if _parse_ts(e.recorded_at) >= lo]
        if filters.date_to is not None:
            hi = _parse_ts(filters.date_to)
            out = [e for e in out if _parse_ts(e.recorded_at) <= hi]
    out.sort(key=lambda e: _parse_ts(e.recorded_at), reverse=(sort != "recorded_at_asc"))
    if limit is not None:
        out = out[:limit]
    return out


class LocalStore(MemoryStore):
    backend_name = "local"

    def __init__(self) -> None:
        # patient_id -> {event_id -> MemoryEvent}, insertion-ordered
        self._events: dict[str, dict[str, MemoryEvent]] = {}
        self._lock = threading.RLock()
        self._persist_path = _resolve_persist_path(settings.MEMORY_LOCAL_PERSIST_PATH)
        self._load_from_disk()

    # -- helpers --------------------------------------------------------------

    def _to_result(self, event: MemoryEvent) -> MemoryResult:
        return MemoryResult(
            fact=_fact_for(event),
            node_type=_NODE_TYPE.get(event.event_type, "Note"),
            recorded_at=event.recorded_at,
            source=event.source,
            verification_status=event.verification.status,
            verified_by=event.verification.by,
            note_id=event.event_id or "",
        )

    def _patient_events(self, patient_id: str) -> list[MemoryEvent]:
        with self._lock:
            return list(self._events.get(patient_id, {}).values())

    def _load_from_disk(self) -> None:
        if not self._persist_path:
            return
        try:
            if not os.path.exists(self._persist_path):
                return
            with open(self._persist_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            loaded: dict[str, dict[str, MemoryEvent]] = {}
            for patient_id, events in raw.items():
                bucket: dict[str, MemoryEvent] = {}
                if not isinstance(events, dict):
                    continue
                for event_id, payload in events.items():
                    if not isinstance(payload, dict):
                        continue
                    event = MemoryEvent.model_validate(payload)
                    bucket[event_id] = event
                loaded[patient_id] = bucket
            self._events = loaded
        except Exception:
            # Corrupt cache should not break API startup; continue with empty memory.
            self._events = {}

    def _flush_to_disk(self) -> None:
        if not self._persist_path:
            return
        directory = os.path.dirname(self._persist_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        snapshot = {
            patient_id: {event_id: event.model_dump(mode="json") for event_id, event in bucket.items()}
            for patient_id, bucket in self._events.items()
        }

        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=True, indent=2)

    # -- MemoryStore interface ------------------------------------------------

    def add_event(self, event: MemoryEvent) -> str:
        eid = event.event_id or f"evt_{uuid4().hex[:12]}"
        stored = event.model_copy(update={"event_id": eid})
        with self._lock:
            self._events.setdefault(event.patient_id, {})[eid] = stored
            self._flush_to_disk()
        return eid

    def query(self, patient_id: str, query_text: str, top_k: int = 5) -> list[MemoryResult]:
        events = self._patient_events(patient_id)
        q_tokens = _tokenize(query_text) - STOPWORDS
        if not q_tokens or not events:
            return []

        known_people = set().union(*(_person_tokens(ev) for ev in events)) if events else set()
        mentioned = q_tokens & known_people

        scored: list[tuple[int, datetime, MemoryEvent]] = []
        for ev in events:
            score = len(q_tokens & _event_tokens(ev))
            if mentioned & _person_tokens(ev):
                score += PEOPLE_BOOST
            if score > 0:
                scored.append((score, _parse_ts(ev.recorded_at), ev))

        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [self._to_result(ev) for _, _, ev in scored[:top_k]]

    def list_memories(
        self,
        patient_id: str,
        filters: ListFilters | None = None,
        sort: str = "recorded_at_desc",
        limit: int | None = None,
    ) -> list[MemoryResult]:
        events = filter_sort_limit(self._patient_events(patient_id), filters, sort, limit)
        return [self._to_result(ev) for ev in events]

    def recent_intake_events(
        self, patient_id: str, medication_name: str, within_minutes: int
    ) -> list[MemoryResult]:
        target = _norm(medication_name)
        matches: list[MemoryEvent] = []
        for ev in self._patient_events(patient_id):
            if ev.event_type != "medication_intake":
                continue
            for m in ev.entities.medications:
                n = _norm(m.name)
                if n == target or target in n or n in target:
                    matches.append(ev)
                    break
        if not matches:
            return []

        matches.sort(key=lambda e: _parse_ts(e.recorded_at), reverse=True)
        reference = _parse_ts(matches[0].recorded_at)
        window = timedelta(minutes=within_minutes)
        recent = [e for e in matches if reference - _parse_ts(e.recorded_at) <= window]
        return [self._to_result(e) for e in recent]

    def set_verification(
        self, patient_id: str, event_id: str, status, by: str | None
    ) -> bool:
        with self._lock:
            event = self._events.get(patient_id, {}).get(event_id)
            if event is None:
                return False
            event.verification.status = status
            event.verification.by = by
            event.verification.at = datetime.now(timezone.utc).isoformat()
            self._flush_to_disk()
            return True

    def consolidate(self, patient_id: str) -> dict:
        groups: dict[str, dict] = {}
        for ev in self._patient_events(patient_id):
            if ev.event_type != "observation":
                continue
            key = _norm_text(ev.transcript or "")
            if not key:
                continue
            group = groups.setdefault(
                key,
                {
                    "pattern": (ev.transcript or "").strip(),
                    "count": 0,
                    "related_note_ids": [],
                    "event_type": "observation",
                },
            )
            group["count"] += 1
            group["related_note_ids"].append(ev.event_id)

        patterns = [g for g in groups.values() if g["count"] >= 2]
        return {"run_id": f"consolidate_{uuid4().hex[:8]}", "patterns": patterns}

    def forget(self, patient_id: str, event_id: str | None = None) -> bool:
        with self._lock:
            bucket = self._events.get(patient_id)
            if bucket is None:
                return False
            if event_id is None:
                if not bucket:
                    return False
                self._events[patient_id] = {}
                self._flush_to_disk()
                return True
            if event_id in bucket:
                del bucket[event_id]
                self._flush_to_disk()
                return True
            return False

    def graph(self, patient_id: str) -> dict:
        events = self._patient_events(patient_id)
        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        patient_node = f"patient:{patient_id}"
        nodes[patient_node] = {"id": patient_node, "type": "Patient", "label": patient_id}

        def add_node(node_id: str, node_type: str, label: str, **extra) -> None:
            if node_id not in nodes:
                nodes[node_id] = {"id": node_id, "type": node_type, "label": label, **extra}

        for ev in events:
            ev_id = ev.event_id or ""
            add_node(
                ev_id,
                _NODE_TYPE.get(ev.event_type, "Note"),
                _fact_for(ev),
                recorded_at=ev.recorded_at,
                source=ev.source,
                verification_status=ev.verification.status,
            )
            edges.append({"source": patient_node, "target": ev_id, "label": "RECORDED"})

            e = ev.entities
            for m in e.medications:
                nid = f"med:{_norm(m.name)}"
                add_node(nid, "Medication", m.name)
                label = "TOOK" if ev.event_type == "medication_intake" else "MENTIONS"
                edges.append({"source": ev_id, "target": nid, "label": label})
            for p in e.people:
                nid = f"person:{_norm(p.name)}"
                add_node(nid, "Person", p.name)
                edges.append({"source": ev_id, "target": nid, "label": "MENTIONS"})
            for pl in e.places:
                nid = f"place:{_norm(pl.name)}"
                add_node(nid, "Place", pl.name)
                edges.append({"source": ev_id, "target": nid, "label": "AT"})
            for o in e.objects:
                nid = f"object:{_norm(o.name)}"
                add_node(nid, "ObjectItem", o.name)
                edges.append({"source": ev_id, "target": nid, "label": "ABOUT"})
                if o.location:
                    lid = f"place:{_norm(o.location)}"
                    add_node(lid, "Place", o.location)
                    edges.append({"source": nid, "target": lid, "label": "LOCATED_AT"})
            for a in e.appointments:
                if a.doctor:
                    did = f"person:{_norm(a.doctor)}"
                    add_node(did, "Person", a.doctor)
                    edges.append({"source": ev_id, "target": did, "label": "WITH"})

        return {"nodes": list(nodes.values()), "edges": edges}
