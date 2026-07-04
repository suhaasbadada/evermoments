# Cognee Memory Engine (Module 3)

Turns structured patient memory events into recallable, caregiver-verifiable answers,
with a pure-Python medication double-dose safety check. Exposed over HTTP at
`/api/memory` and usable offline with zero external dependencies.

## Architecture

```
HTTP  ──►  app/api/memory_routes.py   (/api/memory/*, frozen contract)
             │  (calls only the engine; passes contract types)
             ▼
engine  ──►  app/memory/engine.py     ingest / query / verify / consolidate / forget / graph
             │  (talks ONLY to the MemoryStore interface)
             ▼
store   ──►  app/memory/store.py       MemoryStore ABC + get_store() factory + singleton
             │  backend chosen at runtime by MEMORY_BACKEND
             ├── stores/local_store.py  local  — in-memory, offline, no cognee   (default)
             ├── stores/blob_store.py    blob   — NotImplemented stub (deferred, Slice 9+)
             └── stores/graph_store.py   graph  — cognee hybrid: local embedded OR Cognee Cloud
```

- **Boundary contract** (`app/schemas/memory.py`): `MemoryEvent` in, `MemoryAnswer` out.
  These are the only shapes allowed across the module boundary.
- **`cognee` is imported only** inside `stores/graph_store.py`, lazily — selecting `local`
  (or the `blob` stub, which raises `NotImplementedError` on use) never pulls it in.
- **Double-dose detection** (`app/memory/contradiction.py`) is pure Python (timestamp
  math, no cognee) so it behaves identically on every backend.

## Upstream voice ingestion

The backend-owned voice pipeline lives at `POST /api/ingest/voice-note` and converts a raw
note into the `MemoryEvent` contract used here.

- **Offline/dev path:** send `transcript` directly, or a base64 `text/plain` payload for a
  zero-network STT demo.
- **Real STT path:** set `STT_BACKEND=openai` and `OPENAI_API_KEY`, then send binary audio as
  base64 (`audio/wav`, `audio/mpeg`, `audio/mp4`, `audio/webm`, `audio/ogg`).
- **Handoff:** the ingest pipeline classifies/extracts a `MemoryEvent`, then stores it through
  `engine.ingest_memory_event()` so all provenance, verification, warning, and recall behavior
  stay centralized in Module 3.

## Configuration

Set in `apps/api/.env` (copy from `apps/api/.env.example`). All optional — the API boots
on `local` with no keys.

| Var | Default | Purpose |
|---|---|---|
| `MEMORY_BACKEND` | `local` | `local` \| `blob` \| `graph` |
| `CONTRADICTION_WINDOW_MIN` | `180` | Double-dose look-back window (minutes) |
| `COGNEE_MODE` | `local` | Graph-backend storage: `local` (embedded) \| `cloud` (Cognee Cloud) |
| `COGNEE_CLOUD_URL` | `""` | Cognee Cloud endpoint — **required** for `COGNEE_MODE=cloud` |
| `COGNEE_API_KEY` | `""` | Cognee Cloud key — **required** for `COGNEE_MODE=cloud` |
| `COGNEE_LLM_MODEL` | `gpt-4o-mini` | LLM cognee uses for extraction (graph backend, both modes) |
| `COGNEE_LLM_API_KEY` | `""` | Cognee LLM key (preferred). If blank, backend falls back to `OPENAI_API_KEY` |
| `OPENAI_API_KEY` | `""` | OpenAI-compatible key used by Cognee graph recall/indexing when `COGNEE_LLM_API_KEY` is blank |
| `STT_BACKEND` | `offline` | `offline` \| `openai` for `/api/ingest/voice-note` |
| `STT_MODEL` | `gpt-4o-mini-transcribe` | OpenAI transcription model for binary audio |
| `STT_TIMEOUT_SEC` | `45` | Timeout for the transcription HTTP request |
| `OPENAI_API_KEY` | `""` | Required when `STT_BACKEND=openai` |
| `OPENAI_TRANSCRIBE_URL` | `https://api.openai.com/v1/audio/transcriptions` | Override only if the provider URL changes |

### Graph backend: local (embedded) vs Cognee Cloud

The `graph` backend runs cognee **locally/embedded by default** (`COGNEE_MODE=local`) — graph +
vector storage live on this machine. Set `COGNEE_MODE=cloud` **and** both `COGNEE_CLOUD_URL` +
`COGNEE_API_KEY` to route graph/vector operations to **Cognee Cloud** instead: the store calls
`cognee.serve(url, api_key)` at startup and `cognee.disconnect()` on shutdown.

- **Fallback:** `COGNEE_MODE=cloud` with either cred missing does **not** silently pretend to be
  cloud — it logs a warning and runs the local path. Confirm the live mode at a glance via
  `GET /api/memory/health` → `{"backend":"graph", "mode":"local"|"cloud"}`.
- **What changes:** cloud routes graph/vector reads/writes over the network (added latency) and
  enables cognee auth + multi-tenant; per-patient dataset isolation (`patient_<id>`) holds in both.
- **What doesn't:** the memory contract, `add`/`cognify`/`search(CHUNKS)`/`forget`, the provenance
  join, and the double-dose check are identical in both modes.
- **Key behavior:** Cognee graph recall/indexing needs `COGNEE_LLM_API_KEY` (or `OPENAI_API_KEY` as
  fallback). If both are missing, the graph backend still stores authoritative records and answers via
  deterministic lexical fallback so the API remains available.

## HTTP API (frozen contract)

Base URL: `http://127.0.0.1:8000/api/memory`

| Method & path | Body | Returns |
|---|---|---|
| `GET /health` | — | `{backend, status}` (+ `mode` = `local`\|`cloud` on the graph backend) |
| `POST /events` | `MemoryEvent` | `{event_id, status, warning}` |
| `POST /query` | `{patient_id, query, top_k?}` | `MemoryAnswer` |
| `POST /list` | `{patient_id, filters?, sort?, limit?}` | `{results: MemoryResult[]}` |
| `POST /verify` | `{patient_id, event_id, status, by?}` | `{updated}` (404 if not found) |
| `POST /consolidate` | `{patient_id}` | `{run_id, patterns}` |
| `POST /forget` | `{patient_id, event_id?}` | `{forgot}` |
| `GET /graph/{patient_id}` | — | `{nodes, edges}` |
| `POST /seed` | `{patient_id?}` (p_001 only) | `{patient_id, loaded}` |

### `/list` — enumerate & filter (caregiver dashboard)

`POST /list` returns the **same `MemoryResult` rows** as `/query` (full provenance + current
`verification_status`), read from the authoritative record — identical on `local` and `graph`.

```jsonc
{
  "patient_id": "p_001",
  "filters": {                        // all optional; omit a field to skip that filter
    "event_type": "medication_intake",// EventType: medication_intake | object_location |
                                       //   person_mention | appointment | routine |
                                       //   observation | general
    "verification_status": "unverified", // VerificationStatus: unverified | confirmed |
                                       //   incorrect | needs_check | safety_critical
    "date_from": "2026-06-29T00:00:00Z", // inclusive ISO-8601 lower bound (on recorded_at)
    "date_to":   "2026-07-01T23:59:59Z"  // inclusive ISO-8601 upper bound
  },
  "sort": "recorded_at_desc",         // "recorded_at_desc" (default) | "recorded_at_asc"
  "limit": 20                         // optional positive int; omit for no cap
}
```

Dashboard mapping: **Recent Memories** = no filters; **Pending Verification** =
`verification_status:"unverified"`; **Safety Critical** = `verification_status:"safety_critical"`;
**Medication Notes** = `event_type:"medication_intake"`; **Timeline** = a `date_from`/`date_to`
window with `sort:"recorded_at_asc"`.

### `/consolidate` — pattern insight card

`POST /consolidate` is a pure, idempotent read over the record — safe to call to populate a
dashboard insight card. It returns `{run_id, patterns}` where each pattern is:

```jsonc
{ "pattern": "I felt confused after dinner.", // the repeated text
  "count": 3,                                  // times it recurred (only count >= 2 surface)
  "related_note_ids": ["evt_confused_1", "..."],
  "event_type": "observation" }
```

### Curl walkthrough

```bash
BASE=http://127.0.0.1:8000/api/memory

curl $BASE/health

# Load the p_001 demo dataset
curl -X POST $BASE/seed

# Ask before verification (answer notes it's unconfirmed)
curl -X POST $BASE/query -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","query":"where is my wallet"}'

# List everything for a patient (newest first)
curl -X POST $BASE/list -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001"}'

# Pending Verification: all unverified notes
curl -X POST $BASE/list -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","filters":{"verification_status":"unverified"}}'

# Medication Notes only
curl -X POST $BASE/list -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","filters":{"event_type":"medication_intake"}}'

# Timeline slice: a date range, oldest first, capped at 20
curl -X POST $BASE/list -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","filters":{"date_from":"2026-06-29T00:00:00Z","date_to":"2026-07-01T23:59:59Z"},"sort":"recorded_at_asc","limit":20}'

# Caregiver confirms the wallet note
curl -X POST $BASE/verify -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","event_id":"evt_wallet","status":"confirmed","by":"nurse_amy"}'

# Ingest a 2nd blue pill ~40 min later -> possible_double_dose warning
curl -X POST $BASE/events -H 'Content-Type: application/json' -d '{
  "patient_id":"p_001","event_id":"evt_bluepill_2","source":"voice_note",
  "recorded_at":"2026-07-01T09:10:00Z","event_type":"medication_intake",
  "entities":{"medications":[{"name":"blue pill","form":"tablet"}]}}'

# Surface repeated patterns ("confused after dinner" x3)
curl -X POST $BASE/consolidate -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001"}'

# Typed memory graph
curl $BASE/graph/p_001

# Forget one note
curl -X POST $BASE/forget -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","event_id":"evt_routine"}'
```

## Run the offline demo

```bash
# from apps/api (with the venv active)
PYTHONPATH=. python -m app.memory.seed     # scripted end-to-end trace on the active backend
```

## Testing (two tiers)

The suite is split by cost. **Tier 1 is the default and always free**; Tier 2 is opt-in.

```bash
# one-time: install runtime + test deps (test deps add pytest + httpx for TestClient)
pip install -r requirements.txt -r requirements-dev.txt
```

**Tier 1 — default, free, offline (LocalStore).** The bulk: contract validation, engine,
double-dose (all suppression cases), list/filter, and full HTTP E2E via FastAPI's TestClient.
Makes **zero** network calls — an autouse socket guard fails any test that tries one — so it
never touches the OpenAI key. `cognee`-marked tests are deselected by `pytest.ini`.

```bash
PYTHONPATH=. pytest app/memory             # everything except Tier 2 — $0, no network
```

**Tier 2 — gated, real cognee + OpenAI (costs ~cents, needs a key).** A tiny suite proving only
what can't be shown offline: cognee connect, live ingest→cognify, `SearchType.CHUNKS` recall
with the provenance join, verification reflected in recall, and live forget. One 3-event fixture
is cognified once and reused; the dataset is pruned afterward. Excluded from the default run —
opt in with `-m cognee`. Set a key (`apps/api/.env` → `COGNEE_LLM_API_KEY=…`, or `OPENAI_API_KEY`),
then:

```bash
MEMORY_BACKEND=graph PYTHONPATH=. pytest -m cognee -s app/memory
```

Total OpenAI token usage is printed at the end. Model/embedder stay pinned to `gpt-4o-mini` +
`text-embedding-3-small`.
