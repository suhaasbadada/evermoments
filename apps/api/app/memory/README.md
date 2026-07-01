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
             ├── stores/blob_store.py    blob   — cognee (Slice 7+)
             └── stores/graph_store.py   graph  — cognee (Slice 7+)
```

- **Boundary contract** (`app/schemas/memory.py`): `MemoryEvent` in, `MemoryAnswer` out.
  These are the only shapes allowed across the module boundary.
- **`cognee` is imported only** inside `stores/graph_store.py` / `stores/blob_store.py`,
  lazily — selecting `local` never pulls it in.
- **Double-dose detection** (`app/memory/contradiction.py`) is pure Python (timestamp
  math, no cognee) so it behaves identically on every backend.

## Configuration

Set in `apps/api/.env` (copy from `apps/api/.env.example`). All optional — the API boots
on `local` with no keys.

| Var | Default | Purpose |
|---|---|---|
| `MEMORY_BACKEND` | `local` | `local` \| `blob` \| `graph` |
| `CONTRADICTION_WINDOW_MIN` | `180` | Double-dose look-back window (minutes) |
| `COGNEE_CLOUD_URL` | `""` | Managed Cognee endpoint (Slice 7+, unused on `local`) |
| `COGNEE_API_KEY` | `""` | Managed Cognee key (Slice 7+, unused on `local`) |
| `COGNEE_LLM_MODEL` | `gpt-4o-mini` | LLM cognee uses for extraction (Slice 7+, unused on `local`) |
| `COGNEE_LLM_API_KEY` | `""` | LLM provider key (Slice 7+, unused on `local`) |

## HTTP API (frozen contract)

Base URL: `http://127.0.0.1:8000/api/memory`

| Method & path | Body | Returns |
|---|---|---|
| `GET /health` | — | `{backend, status}` |
| `POST /events` | `MemoryEvent` | `{event_id, status, warning}` |
| `POST /query` | `{patient_id, query, top_k?}` | `MemoryAnswer` |
| `POST /verify` | `{patient_id, event_id, status, by?}` | `{updated}` (404 if not found) |
| `POST /consolidate` | `{patient_id}` | `{run_id, patterns}` |
| `POST /forget` | `{patient_id, event_id?}` | `{forgot}` |
| `GET /graph/{patient_id}` | — | `{nodes, edges}` |
| `POST /seed` | `{patient_id?}` (p_001 only) | `{patient_id, loaded}` |

### Curl walkthrough

```bash
BASE=http://127.0.0.1:8000/api/memory

curl $BASE/health

# Load the p_001 demo dataset
curl -X POST $BASE/seed

# Ask before verification (answer notes it's unconfirmed)
curl -X POST $BASE/query -H 'Content-Type: application/json' \
  -d '{"patient_id":"p_001","query":"where is my wallet"}'

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

## Run the offline demo & tests

```bash
# from apps/api (with the repo .venv active)
PYTHONPATH=. python -m app.memory.seed     # scripted end-to-end trace on the active backend
pytest app/memory                          # module test suite
```
