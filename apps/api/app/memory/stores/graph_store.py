"""CogneeGraphStore: the PRIMARY (graph) MemoryStore backend, powered by cognee.

Design (see the Slice-7 spike for the empirical basis):

cognee 1.2.2 gives us a real knowledge-graph + embedding recall layer, but every
provenance field the contract requires (``source``, ``recorded_at``,
``verification_status``, ``verified_by``, ``note_id``, ``node_type``) is OUR
structured metadata, not anything cognee's LLM produces. Verification is mutable,
double-dose detection must be exact timestamp math, and consolidation must be
deterministic (guardrail #5). So this backend is a hybrid:

* An in-memory **authoritative event record** (same shape as ``LocalStore``) is the
  source of truth for provenance, verification, double-dose, consolidation, graph
  export, and single-item forget.
* **cognee powers semantic recall in ``query()``** — the "recall via Cognee" loop, now
  HYBRID (Fix 1). We ingest each event's text tagged with a ``[ref:<event_id>]`` sentinel.
  * FACTUAL lookups ("where is my wallet") retrieve with ``SearchType.CHUNKS`` (embedding
    similarity), parse the sentinel out of the chunks, and join back to the authoritative
    record for full, current provenance.
  * RELATIONAL/connective questions ("who is Ravi", "what relates to the confusion")
    TRAVERSE the graph with ``SearchType.GRAPH_COMPLETION`` — which composes an answer over
    the graph the temporal cognify built. That answer is sourceless prose, so it rides as a
    ``GraphAnswer`` lead row (empty ``note_id``, ``unverified``) with the CHUNKS-joined events
    attached beneath it, keeping supporting provenance verifiable. Routing (``_is_relational``)
    is pure/deterministic; the factual path is unchanged.

``cognee`` is imported ONLY in this module (guardrail #1). Its heavy import is paid
only when ``MEMORY_BACKEND=graph`` selects this backend (lazy import in
``store.get_store()``).
"""

import asyncio
import atexit
import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import settings
from app.memory.store import MemoryStore

# Reuse LocalStore's PURE, stateless helpers so fact phrasing and node typing are
# byte-for-byte identical across backends. Importing them does not touch LocalStore's
# behaviour (guardrail: other backends untouched).
from app.memory.stores.local_store import (
    PEOPLE_BOOST,
    STOPWORDS,
    _NODE_TYPE,
    _event_tokens,
    _fact_for,
    _norm,
    _norm_text,
    _parse_ts,
    _person_tokens,
    _tokenize,
    filter_sort_limit,
)
from app.schemas.memory import ListFilters, MemoryEvent, MemoryResult

logger = logging.getLogger(__name__)

# --- Mode selection + operational env (MUST be set before `import cognee`) ---------
# COGNEE_MODE=cloud routes graph/vector ops to Cognee Cloud via serve(); anything else — or
# cloud without both creds — runs the local/embedded path. _CLOUD is decided here, AT IMPORT,
# so the local-only env overrides below are applied whenever we are NOT cloud-ready. That way
# the missing-creds fallback lands on a correctly-configured local path (no late os.environ set).
_MODE = (settings.COGNEE_MODE or "local").strip().lower()
_CLOUD = _MODE == "cloud" and bool(settings.COGNEE_CLOUD_URL) and bool(settings.COGNEE_API_KEY)

# litellm reads OPENAI_API_KEY — OpenAI is the LLM egress in BOTH modes.
def _resolve_llm_key() -> str:
    """Resolve the LLM key for cognee config.

    Priority: explicit COGNEE_LLM_API_KEY, then OPENAI_API_KEY for convenience.
    """
    return (
        settings.COGNEE_LLM_API_KEY
        or os.environ.get("COGNEE_LLM_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
    )


_llm_key = _resolve_llm_key()
if _llm_key:
    os.environ.setdefault("OPENAI_API_KEY", _llm_key)
if not _CLOUD:
    # Local/embedded single-user only: access control off, and bypass the pre-flight LLM
    # connection test (it retries-to-timeout on any error). Cloud keeps auth + the test intact.
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")

import cognee  # noqa: E402
from cognee.modules.search.types import SearchType  # noqa: E402

# Sentinel appended to each ingested chunk so retrieval can be joined to our record.
_REF_RE = re.compile(r"\[ref:([^\]]+)\]")

_configured = False
_config_lock = threading.Lock()


def _init_cognee_once() -> None:
    """Configure cognee's LLM + embedder once (idempotent). Never logs secrets."""
    global _configured
    if _configured:
        return
    with _config_lock:
        if _configured:
            return
        key = _resolve_llm_key()
        model = settings.COGNEE_LLM_MODEL or os.environ.get("COGNEE_LLM_MODEL", "gpt-4o-mini")
        try:
            if key:
                cognee.config.set_llm_api_key(key)
                cognee.config.set_embedding_api_key(key)
            cognee.config.set_llm_model(model)
            # Pin the cheap embedder (Slice-7 default was the pricier -3-large).
            cognee.config.set_embedding_model("text-embedding-3-small")
            try:
                cognee.config.set_embedding_dimensions(1536)
            except Exception:  # dimensions may be auto-derived; non-fatal
                pass
        except Exception as e:  # pragma: no cover - config surface varies
            logger.warning("cognee LLM/embedding config issue: %s", e)

        # Optional (local/embedded only): keep patient data out of the repo / default cache via
        # COGNEE_DATA_DIR. In cloud mode storage is remote, so local-dir pinning does not apply.
        data_dir = os.environ.get("COGNEE_DATA_DIR")
        if not _CLOUD and data_dir:
            try:
                cognee.config.data_root_directory(os.path.join(data_dir, "data"))
                cognee.config.system_root_directory(os.path.join(data_dir, "system"))
            except Exception as e:
                logger.warning("cognee data dir config issue: %s", e)

        _configured = True
        logger.info(
            "CogneeGraphStore configured (model=%s, embedder=text-embedding-3-small)", model
        )


_bg_loop = None
_bg_lock = threading.Lock()


def _background_loop():
    """A single, process-wide event loop on a daemon thread.

    cognee caches loop-bound state (async locks, DB engines, aiohttp sessions), so
    every coroutine must run on the SAME loop. Calling ``asyncio.run()`` per call
    would bind that state to a loop that is then closed, so the next cognify/search
    fails with "bound to a different event loop". One long-lived loop avoids that and
    is safe to drive from FastAPI's sync route threadpool.
    """
    global _bg_loop
    if _bg_loop is not None:
        return _bg_loop
    with _bg_lock:
        if _bg_loop is None:
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, name="cognee-loop", daemon=True).start()
            _bg_loop = loop
        return _bg_loop


def _run(coro):
    """Marshal a cognee coroutine onto the shared background loop and block for it."""
    return asyncio.run_coroutine_threadsafe(coro, _background_loop()).result()


def _run_maybe_async(value):
    """serve()/disconnect() may be sync or a coroutine (per cognee version). Run either on the
    shared background loop, so a cloud connection binds to the same loop add/cognify/search use."""
    return _run(value) if asyncio.iscoroutine(value) else value


def _event_body(event: MemoryEvent) -> str:
    """The searchable text ingested for an event (transcript + concise fact)."""
    parts: list[str] = []
    if event.transcript:
        parts.append(event.transcript.strip())
    fact = _fact_for(event)
    if fact and (not event.transcript or fact.lower() not in event.transcript.lower()):
        parts.append(fact)
    return " ".join(p for p in parts if p) or event.event_type.replace("_", " ")


def _extract_texts(raw) -> list[str]:
    """Pull chunk texts out of whatever shape cognee.search returns (defensive)."""
    texts: list[str] = []

    def walk(o) -> None:
        if o is None:
            return
        if isinstance(o, str):
            texts.append(o)
            return
        if isinstance(o, dict):
            t = o.get("text")
            if isinstance(t, str):
                texts.append(t)
            else:
                for v in o.values():
                    walk(v)
            return
        if isinstance(o, (list, tuple, set)):
            for v in o:
                walk(v)
            return
        # object: SearchResult{search_result,...} / SearchResultItem{text,...}
        t = getattr(o, "text", None)
        if isinstance(t, str):
            texts.append(t)
        sr = getattr(o, "search_result", None)
        if sr is not None and sr is not o:
            walk(sr)

    walk(raw)
    return texts


# --- Hybrid query routing (Fix 1) -------------------------------------------
# Relational/connective questions ("who is Ravi", "how are Ravi and the confusion related",
# "why did I feel confused") are answered by TRAVERSING the knowledge graph via
# SearchType.GRAPH_COMPLETION, which composes an answer over the graph. Factual lookups
# ("where is my wallet", "when is my appointment") stay on CHUNKS + the [ref:] provenance
# join, because GRAPH_COMPLETION returns sourceless prose (no source/verification/note_id).
#
# The default is FACTUAL — the provenance-preserving path — so only confident relational
# signals route to the graph. A leading factual wh-word (where/when/how many/how much/what
# time) overrides a relational token, since those questions need the exact, source-backed
# answer the provenance join gives. _is_relational is PURE (no cognee) so Tier 1 unit-tests
# the routing offline with zero network.
_RELATIONAL_RE = re.compile(
    r"""(?xi)
      \bwho\b                                 # who is / who are / who visited ...
    | \bwhose\b
    | \brelat(?:e|es|ed|ing|ion|ionship)\b    # relate / related / relationship
    | \bconnect(?:ed|ion|ions|s)?\b           # connect / connected / connection
    | \blinked?\b                             # link / linked
    | \bassociat(?:e|ed|ion)\b                # associate / associated
    | \bwhy\b                                  # why did I ...  (causal / connective)
    | \bhow\ (?:is|are|was|were|do|does|did)\b .* \b(?:relat|connect|know|link|associat)
    | \btell\ me\ about\b
    | \bwhat\ relates?\b
    | \bwhat\ (?:is|was|are|'?s)\ .*\b(?:relationship|connection|link)\b
    """
)

# A leading factual wh-word forces the CHUNKS + provenance path even if a relational token
# also appears (e.g. "where did Ravi put the wallet" is a location lookup, not a graph walk).
_FACTUAL_LEAD_RE = re.compile(r"(?i)^\s*(?:where|when|what\s+time|how\s+many|how\s+much)\b")


def _is_relational(query_text: str) -> bool:
    """Route a question: True -> traverse the graph (GRAPH_COMPLETION); False -> CHUNKS.

    Deterministic and pure so routing is testable without cognee. Factual wh-questions win
    over a relational token, because they need the exact, source-backed provenance answer."""
    q = (query_text or "").strip()
    if not q:
        return False
    if _FACTUAL_LEAD_RE.search(q):
        return False
    return bool(_RELATIONAL_RE.search(q))


def _completion_prose(raw) -> str:
    """Extract the composed answer from a *_COMPLETION result and normalise it to one calm
    line. GRAPH_COMPLETION can return multi-line markdown; the engine uses this as the lead
    sentence of a patient-facing answer, so it must be a single tidy string.

    Targets ONLY the answer payload: the Cognee-Cloud envelope wraps it as
    ``[{'search_result': ['<prose>']}, ...]`` (and dict items may be ``{'text'|'value': ...}``);
    unlike ``_extract_texts`` we do NOT sweep sibling keys like ``dataset_id`` into the text."""
    strings: list[str] = []

    def collect(o) -> None:
        if o is None:
            return
        if isinstance(o, str):
            strings.append(o)
            return
        if isinstance(o, dict):
            if "search_result" in o:  # cloud envelope: descend ONLY into the payload
                collect(o["search_result"])
                return
            for key in ("text", "value", "answer"):  # completion item shapes
                v = o.get(key)
                if isinstance(v, str):
                    strings.append(v)
                    return
            return
        if isinstance(o, (list, tuple, set)):
            for v in o:
                collect(v)
            return
        t = getattr(o, "text", None)  # SearchResultItem-like object
        if isinstance(t, str):
            strings.append(t)
            return
        sr = getattr(o, "search_result", None)
        if sr is not None and sr is not o:
            collect(sr)

    collect(raw)
    text = " ".join(s.strip() for s in strings if isinstance(s, str) and s.strip())
    if not text:
        return ""
    # Flatten markdown emphasis/headings/bullets and any newlines into a single line.
    text = re.sub(r"[*_#>`]+", " ", text)
    text = re.sub(r"(?m)^\s*[-•]\s*", " ", text)
    text = re.sub(r"\s*[\r\n]+\s*[-•]?\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


class CogneeGraphStore(MemoryStore):
    backend_name = "graph"

    def __init__(self) -> None:
        # Authoritative record: patient_id -> {event_id -> MemoryEvent}
        self._events: dict[str, dict[str, MemoryEvent]] = {}
        # patient_id -> {event_id -> ingested body text} (query fallback join)
        self._ingest_texts: dict[str, dict[str, str]] = {}
        # patient_id -> {event_id -> cognee data_id} (best-effort single-item forget)
        self._data_ids: dict[str, dict[str, object]] = {}
        # patients with un-cognified adds (lazy, batched cognify on read)
        self._dirty: set[str] = set()
        self._lock = threading.RLock()
        self._cognee_ready = bool(_resolve_llm_key())

        if not self._cognee_ready:
            logger.warning(
                "COGNEE_LLM_API_KEY/OPENAI_API_KEY not set; graph backend will store "
                "authoritative records and use deterministic fallback recall until a key is set."
            )

        # Connection mode surfaced by GET /api/memory/health. "cloud" only when actually
        # cloud-ready; a cloud request without both creds falls back to "local" (with a warning),
        # so we never *think* we're on cloud when we're not.
        self.mode = "cloud" if _CLOUD else "local"
        self._connected = False
        if _MODE == "cloud" and not _CLOUD:
            logger.warning(
                "COGNEE_MODE=cloud but COGNEE_CLOUD_URL/COGNEE_API_KEY are not both set — "
                "running the LOCAL/embedded path instead (set both creds to use Cognee Cloud)."
            )
        elif _CLOUD:
            self._connect_cloud()

    # -- cloud connection lifecycle -------------------------------------------

    def _connect_cloud(self) -> None:
        """Open the Cognee Cloud connection via serve() at startup (cloud mode only).

        Lets serve() errors propagate: if creds ARE set but the connection fails, we fail loud
        rather than quietly degrade. serve() takes only url + api_key (no tenant_id)."""
        _init_cognee_once()  # LLM/embedder config applies in both modes
        _run_maybe_async(
            cognee.serve(url=settings.COGNEE_CLOUD_URL, api_key=settings.COGNEE_API_KEY)
        )
        self._connected = True
        atexit.register(self.close)
        logger.info("CogneeGraphStore connected to Cognee Cloud at %s", settings.COGNEE_CLOUD_URL)

    def close(self) -> None:
        """Disconnect from Cognee Cloud on teardown/shutdown. Idempotent + best-effort."""
        if not self._connected:
            return
        self._connected = False
        try:
            _run_maybe_async(cognee.disconnect())
        except Exception as e:  # atexit runs during interpreter shutdown; never raise
            logger.debug("cognee.disconnect() skipped: %s", e)

    # -- helpers --------------------------------------------------------------

    def _dataset(self, patient_id: str) -> str:
        """One cognee dataset per patient — the isolation boundary (guardrail)."""
        return f"patient_{patient_id}"

    def _patient_events(self, patient_id: str) -> list[MemoryEvent]:
        with self._lock:
            return list(self._events.get(patient_id, {}).values())

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

    def _capture_data_id(self, patient_id: str, eid: str, add_result) -> None:
        """Best-effort: map our event_id -> cognee data_id for single-item forget."""
        try:
            dsid = getattr(add_result, "dataset_id", None)
            if dsid is None and isinstance(add_result, dict):
                dsid = add_result.get("dataset_id")
            if dsid is None:
                return
            from cognee.modules.data.methods import get_last_added_data

            data = _run(get_last_added_data(dsid))
            did = getattr(data, "id", None) if data is not None else None
            if did is not None:
                with self._lock:
                    self._data_ids.setdefault(patient_id, {})[eid] = did
        except Exception as e:  # never let bookkeeping break ingest
            logger.debug("data_id capture skipped for %s: %s", eid, e)

    def _ensure_cognified(self, patient_id: str) -> None:
        """Batch-cognify a patient's pending adds once (temporal flag per directive)."""
        if not self._cognee_ready:
            return
        with self._lock:
            if patient_id not in self._dirty:
                return
        ds = self._dataset(patient_id)
        try:
            _run(cognee.cognify(datasets=[ds], temporal_cognify=True))
            with self._lock:
                self._dirty.discard(patient_id)
        except Exception as e:
            # Leave dirty; query degrades to empty recall (engine handles it).
            logger.warning("cognee.cognify failed for %s: %s", patient_id, e)

    # -- MemoryStore interface ------------------------------------------------

    def add_event(self, event: MemoryEvent) -> str:
        eid = event.event_id or f"evt_{uuid4().hex[:12]}"
        stored = event if event.event_id else event.model_copy(update={"event_id": eid})
        body = _event_body(stored)
        with self._lock:
            self._events.setdefault(event.patient_id, {})[eid] = stored
            self._ingest_texts.setdefault(event.patient_id, {})[eid] = body
            self._dirty.add(event.patient_id)

        if not self._cognee_ready:
            return eid

        _init_cognee_once()

        ds = self._dataset(event.patient_id)
        text = f"{body} [ref:{eid}]"
        try:
            result = _run(cognee.add(text, dataset_name=ds, node_set=[eid]))
            self._capture_data_id(event.patient_id, eid, result)
        except Exception as e:
            logger.warning("cognee.add failed for %s: %s", eid, e)
        return eid

    def query(self, patient_id: str, query_text: str, top_k: int = 5) -> list[MemoryResult]:
        """Hybrid recall (Fix 1). Relational/connective questions traverse the knowledge
        graph (GRAPH_COMPLETION); factual lookups keep CHUNKS + the provenance join.

        Both return the same ``MemoryResult`` contract. On the relational path the graph
        composes a sourceless prose answer, so we carry it as a ``GraphAnswer`` lead row
        (no ``note_id``, ``unverified``) and attach the CHUNKS-joined events beneath it with
        their real, current provenance — verifiable exactly like the factual path."""
        with self._lock:
            events = dict(self._events.get(patient_id, {}))
        if not events:
            return []

        if not self._cognee_ready:
            return self._fallback_query(events, query_text, top_k)

        _init_cognee_once()

        self._ensure_cognified(patient_id)
        ds = self._dataset(patient_id)
        if _is_relational(query_text):
            return self._relational_query(patient_id, query_text, top_k, ds, events)
        return self._chunks_query(patient_id, query_text, top_k, ds, events)

    def _fallback_query(
        self,
        events: dict[str, MemoryEvent],
        query_text: str,
        top_k: int,
    ) -> list[MemoryResult]:
        """Deterministic lexical fallback used when cognee recall is unavailable."""
        q_tokens = _tokenize(query_text) - STOPWORDS
        if not q_tokens or not events:
            return []

        all_events = list(events.values())
        known_people = set().union(*(_person_tokens(ev) for ev in all_events)) if all_events else set()
        mentioned = q_tokens & known_people

        scored: list[tuple[int, datetime, MemoryEvent]] = []
        for ev in all_events:
            score = len(q_tokens & _event_tokens(ev))
            if mentioned & _person_tokens(ev):
                score += PEOPLE_BOOST
            if score > 0:
                scored.append((score, _parse_ts(ev.recorded_at), ev))

        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [self._to_result(ev) for _, _, ev in scored[:top_k]]

    def _relational_query(
        self,
        patient_id: str,
        query_text: str,
        top_k: int,
        ds: str,
        events: dict[str, MemoryEvent],
    ) -> list[MemoryResult]:
        """Traverse the graph for a composed answer, then attach CHUNKS provenance beneath it."""
        prose = self._graph_completion(ds, query_text, top_k)
        # Supporting evidence: the SAME CHUNKS + [ref:] join the factual path uses, so the
        # events the answer draws on stay caregiver-verifiable with full, current provenance.
        support = self._chunks_query(patient_id, query_text, top_k, ds, events)
        if not prose:
            # Graph answer unavailable (composition failed / empty) -> degrade to the
            # provenance-backed factual result rather than return nothing.
            return support

        # The composed answer is genuinely sourceless: node_type marks it, note_id is empty,
        # and it is never caregiver-confirmed. (source is a closed Literal with no "graph"
        # value, so we borrow the strongest supporting row's source, else the common default.)
        lead = MemoryResult(
            fact=prose,
            node_type="GraphAnswer",
            recorded_at=datetime.now(timezone.utc).isoformat(),
            source=support[0].source if support else "voice_note",
            verification_status="unverified",
            verified_by=None,
            note_id="",
        )
        return [lead, *support[: max(top_k - 1, 0)]]

    def _graph_completion(self, ds: str, query_text: str, top_k: int) -> str:
        """Run SearchType.GRAPH_COMPLETION and return the composed answer as one calm line."""
        try:
            raw = _run(
                cognee.search(
                    query_text=query_text,
                    query_type=SearchType.GRAPH_COMPLETION,
                    datasets=[ds],
                    top_k=max(top_k, 5),
                )
            )
        except Exception as e:
            logger.warning("cognee GRAPH_COMPLETION failed for %s: %s", ds, e)
            return ""
        return _completion_prose(raw)

    def _chunks_query(
        self,
        patient_id: str,
        query_text: str,
        top_k: int,
        ds: str,
        events: dict[str, MemoryEvent],
    ) -> list[MemoryResult]:
        """Factual path: CHUNKS embedding recall joined to the authoritative record via the
        ``[ref:<id>]`` sentinel. UNCHANGED from the original query() — full provenance."""
        try:
            raw = _run(
                cognee.search(
                    query_text=query_text,
                    query_type=SearchType.CHUNKS,
                    datasets=[ds],
                    top_k=max(top_k * 3, 12),
                )
            )
        except Exception as e:
            logger.warning("cognee.search failed for %s: %s", patient_id, e)
            return self._fallback_query(events, query_text, top_k)

        texts = _extract_texts(raw)
        ordered: list[str] = []
        seen: set[str] = set()

        # Primary join: the [ref:<id>] sentinel carried through the chunk text.
        for t in texts:
            for ref in _REF_RE.findall(t):
                if ref in events and ref not in seen:
                    seen.add(ref)
                    ordered.append(ref)

        # Fallback join (if the sentinel didn't survive): match stored body text.
        if not ordered:
            norm_chunks = [_norm_text(t) for t in texts]
            bodies = self._ingest_texts.get(patient_id, {})
            for eid, ev in events.items():
                body = _norm_text(bodies.get(eid) or _fact_for(ev))
                if body and any(body in nc or nc in body for nc in norm_chunks):
                    if eid not in seen:
                        seen.add(eid)
                        ordered.append(eid)

        # Precision guard: cognee ranks by semantic similarity, but CHUNKS returns the
        # k nearest regardless of true relevance. Keep only results that share a
        # meaningful term with the query (same relevance rule as LocalStore, so the
        # result SET is consistent across backends while cognee provides the ordering).
        q_tokens = _tokenize(query_text) - STOPWORDS
        if q_tokens:
            ordered = [eid for eid in ordered if q_tokens & _event_tokens(events[eid])]

        if not ordered:
            return self._fallback_query(events, query_text, top_k)

        return [self._to_result(events[i]) for i in ordered[:top_k]]

    def list_memories(
        self,
        patient_id: str,
        filters: ListFilters | None = None,
        sort: str = "recorded_at_desc",
        limit: int | None = None,
    ) -> list[MemoryResult]:
        # Record-only operation: enumeration/filtering reads the authoritative record (never
        # cognee), so /list is identical to LocalStore across backends — no cognify/search here.
        events = filter_sort_limit(self._patient_events(patient_id), filters, sort, limit)
        return [self._to_result(ev) for ev in events]

    def recent_intake_events(
        self, patient_id: str, medication_name: str, within_minutes: int
    ) -> list[MemoryResult]:
        # Deterministic timestamp math over the authoritative record (guardrail #5).
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

    def set_verification(self, patient_id: str, event_id: str, status, by: str | None) -> bool:
        with self._lock:
            event = self._events.get(patient_id, {}).get(event_id)
            if event is None:
                return False
            event.verification.status = status
            event.verification.by = by
            event.verification.at = datetime.now(timezone.utc).isoformat()
            return True

    def consolidate(self, patient_id: str) -> dict:
        # Deterministic pattern detection over repeated observations.
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
        _init_cognee_once()
        did = None
        with self._lock:
            bucket = self._events.get(patient_id) or {}
            if event_id is None:
                removed = bool(bucket)
                self._events[patient_id] = {}
                self._ingest_texts.pop(patient_id, None)
                self._data_ids.pop(patient_id, None)
                self._dirty.discard(patient_id)
            else:
                removed = event_id in bucket
                if removed:
                    del bucket[event_id]
                    self._ingest_texts.get(patient_id, {}).pop(event_id, None)
                    did = (self._data_ids.get(patient_id) or {}).pop(event_id, None)

        # cognee side effects (best-effort; correctness holds via record join-gating).
        ds = self._dataset(patient_id)
        if event_id is None:
            try:
                _run(cognee.forget(dataset=ds))
            except Exception as e:
                logger.warning("cognee.forget(dataset=%s) skipped: %s", ds, e)
        elif did is not None:
            try:
                # data_id delete also requires the dataset scope (per cognee 1.2.2).
                _run(cognee.forget(data_id=did, dataset=ds))
            except Exception as e:
                logger.warning("cognee single-item forget skipped for %s: %s", event_id, e)
        return removed

    def graph(self, patient_id: str) -> dict:
        # Typed nodes + labelled edges built from the authoritative record, using the
        # same helpers as LocalStore so the exported shape is identical across backends.
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
                    did_node = f"person:{_norm(a.doctor)}"
                    add_node(did_node, "Person", a.doctor)
                    edges.append({"source": ev_id, "target": did_node, "label": "WITH"})

        return {"nodes": list(nodes.values()), "edges": edges}
