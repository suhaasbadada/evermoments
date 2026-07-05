# Evermoments — Patient App (Module 1)

Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · App Router

---

## Quick start

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

Copy the env file and fill in the memory API URL (see Integration below):

```bash
cp .env.example .env.local
```

---

## What is built

### Screens

| Route | Screen | Status |
|---|---|---|
| `/` | Patient Home — 4 big buttons + Demo Evening Mode toggle | ✅ done |
| `/record` | Record a Memory — mic → mock STT → confirm → save | ✅ done |
| `/ask` | Ask My Memory — example chips + text input → answer card | ✅ done |
| `/memories` | Today's Memories — lists all stored memories with badges | ✅ done |

### Sundowning / Safe Mode
Built into the home screen. Auto-activates after 6 pm local time. Also has a manual **Demo: Evening Mode** toggle for judging. Safe mode shows:
- Large clock and date orientation card ("You are safe")
- Only Record and Ask buttons visible
- Calm dark indigo palette

### Memory client (`src/lib/memoryClient.ts`)
Full TypeScript client for the Module 3 contract. All 9 functions:

```
checkMemoryHealth()      ingestMemoryEvent()    queryMemory()
listMemories()           verifyMemory()         consolidateMemory()
forgetMemory()           getMemoryGraph()       seedPatient()
```

All interfaces match the Module 3 Pydantic schemas 1-to-1 (`MemoryEvent`, `MemoryResult`, `MemoryAnswer`, `MemoryWarning`, `VerificationStatus`, etc.).

### Mock voice backend (`src/lib/mockVoiceBackend.ts`)
Stands in for Module 2 (STT + entity extraction). Returns a `Partial<MemoryEvent>` after a fake 800–1500 ms delay. Cycles through 3 examples:

| What you say | Event type | Entities |
|---|---|---|
| *(anything — 1st tap)* | `object_location` | wallet → top drawer |
| *(anything — 2nd tap)* | `medication_intake` | blue pill, after breakfast |
| *(anything — 3rd tap)* | `person_mention` | Ravi, 5 pm pickup |

Swap `mockTranscribeAndExtract(blob)` for a real `fetch` to `/api/stt` (Module 2) and nothing else in the UI changes.

### Safety layer
- `IngestResponse.warning` (single `MemoryWarning`) is shown immediately after save as an orange banner — double-dose detection surfaces right on the confirmation screen.
- `MemoryAnswer.warnings[]` shown before the answer on the Ask screen.
- `VerificationBadge` renders all five statuses (`unverified`, `confirmed`, `incorrect`, `needs_check`, `safety_critical`) with colour coding on every memory card.

### Built-in mock API routes
When `NEXT_PUBLIC_MEMORY_API_URL=http://localhost:3000` (same origin), the app routes all memory calls to Next.js route handlers that keep an in-memory store. Resets on server restart — expected for local dev.

```
GET  /api/memory/health
POST /api/memory/events        ← double-dose warning logic included
POST /api/memory/query         ← keyword search + natural-language answer
POST /api/memory/list          ← filters, sort, limit
POST /api/memory/verify
POST /api/memory/consolidate
POST /api/memory/forget
GET  /api/memory/graph/[patient_id]
POST /api/memory/seed          ← loads 5 canned events for p_001
```

On home-screen load the app calls `GET /health` then `POST /seed` (patient `p_001`) so Ask My Memory has data immediately without manual setup.

---

## Integrating with Module 3 (Cognee Memory Engine)

**One line change** — everything else is already wired.

### Step 1 — Start the Module 3 server

```bash
git checkout feat/cognee-memory-engine
# follow that module's README for env vars and startup
uvicorn app.main:app --reload --port 8000
```

### Step 2 — Point the patient app at it

Edit `apps/web/.env.local`:

```env
# Was: http://localhost:3000  (same-origin mock)
NEXT_PUBLIC_MEMORY_API_URL=http://localhost:8000
```

Restart `npm run dev`. The health indicator in the top-right corner will turn green and show `Memory connected · local` (or `· cloud` if `MEMORY_BACKEND=graph`).

### Step 3 — Confirm CORS

Module 3's FastAPI app must allow the patient app's origin. Add to `app/main.py` if not already there:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Step 4 — Swap Module 2 (STT) when ready

In `src/app/record/page.tsx`, find:

```ts
const partial = await mockTranscribeAndExtract(blob);
```

Replace with a call to the real Module 2 endpoint:

```ts
const formData = new FormData();
formData.append("audio", blob, "recording.webm");
const res = await fetch("http://localhost:8000/api/stt", { method: "POST", body: formData });
const partial = await res.json() as Partial<MemoryEvent>;
```

The rest of the save flow (`ingestMemoryEvent`, warning display, success screen) stays exactly the same.

---

## Environment variables

| Variable | Default in `.env.local` | Purpose |
|---|---|---|
| `NEXT_PUBLIC_MEMORY_API_URL` | `http://localhost:3000` | Base URL for Module 3. Set to `http://localhost:8000` for live backend. |

---

## Known dev setup note — Tailwind CSS

Tailwind v4's PostCSS plugin (`@tailwindcss/postcss`) requires a Windows-specific native binary (`lightningcss-win32-x64-msvc`) that is not yet installed. Until `npm install` can reach the registry:

- `postcss.config.mjs` has the `@tailwindcss/postcss` plugin disabled
- `globals.css` has the `@import "tailwindcss"` directive removed
- A `TailwindLoader` client component loads the Tailwind Play CDN after React hydration

**To restore the proper build pipeline** once network access is available:

```bash
cd apps/web && npm install   # installs the missing native binary
```

Then revert `postcss.config.mjs` to:
```js
const config = { plugins: { "@tailwindcss/postcss": {} } };
export default config;
```

Revert `globals.css` first line to:
```css
@import "tailwindcss";
```

Remove `<TailwindLoader />` from `layout.tsx` and its import.

---

## Patient ID

Hardcoded to `p_001` for the hackathon demo. Search for `PATIENT_ID` in `src/app/` to update all screens at once when auth is added.
