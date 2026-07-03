# Integration Checklist — End-to-End Verification

Owner: Member 4. Run this after all four modules are wired together
(`NEXT_PUBLIC_USE_MOCK_MEMORY=false`, Japit's `/memory/*` endpoints live,
Member 2's pipeline ingesting real audio).

The whole checklist is one continuous story — the double-dose scenario — so
you can run it top to bottom as a single rehearsal. It is also the demo script
skeleton. Patient: `p_001`. Caregiver: Ravi.

---

## Pre-flight (before the walkthrough)

- [ ] `apps/api` backend is up and `/memory/list`, `/memory/query`,
      `/memory/verify`, `/memory/consolidate`, `DELETE /memory` all respond
      (not 404) — Japit
- [ ] Cognee Cloud connection is live (`cognee.serve()` succeeds at startup,
      check backend logs) — Japit
- [ ] STT works: a test audio clip comes back as a transcript — Member 2
- [ ] `apps/web/.env.local` has `NEXT_PUBLIC_USE_MOCK_MEMORY=false` — Member 4
- [ ] Contract confirmations from Japit (blockers if wrong, silent failures not errors):
  - [ ] `/memory/consolidate` response carries surfaced patterns as
        `patterns: string[]` (else the consolidate panel shows zero bullets)
  - [ ] `/memory/list` items carry the `warning` object on safety-critical
        notes (else the dashboard shows only a badge, no double-dose message)
  - [ ] `/memory/list` items include `event_type` (else timeline category
        chips and the Medication tab filter nothing)

---

## The end-to-end example: one memory, module by module

### Step 1 — Module 1 (Patient App): record the first dose
Patient taps **Record Memory** and says:
> "I took the blue pill after breakfast."

- [ ] Recording UI captures audio and shows the transcript back
- [ ] Patient confirms "Save this memory" and gets a calm confirmation
- [ ] No error toast; note the time (call it ~8:30 AM)

### Step 2 — Module 2 (Backend/STT/Extraction): audio becomes a MemoryEvent
Behind the scenes — verify via backend logs or DB:

- [ ] Transcript matches what was said (close enough: "blue pill", "breakfast")
- [ ] Extracted `MemoryEvent` has `event_type: "medication_intake"`,
      a medication entity ("blue pill"), and a valid ISO `recorded_at`
- [ ] Event was POSTed to `/memory/ingest` and got `{event_id, status}` back

### Step 3 — Module 3 (Cognee Engine): the graph remembers
- [ ] Japit's logs show DataPoints created (Note + IntakeEvent), not a raw
      text blob
- [ ] `GET /memory/graph?patient_id=p_001` shows the new nodes/edges
- [ ] No contradiction warning yet (this is the first dose today)

### Step 4 — Module 1 again: record the *duplicate* dose
An hour-ish later (or with a faked timestamp), patient records:
> "I took the blue pill."

- [ ] Ingest response now carries the `possible_double_dose` warning
      (Module 3's application-layer time-window check fired)
- [ ] Module 1 immediately shows the gentle warning: already recorded at
      8:30 AM, please check with caregiver — calm wording, not alarming

### Step 5 — Module 1: patient asks their memory
Patient asks via **Ask My Memory**:
> "Did I take my medicine today?"

- [ ] Answer comes from `recall()` and mentions the blue pill with the time
- [ ] Answer card shows provenance: source (voice note), recorded time,
      caregiver status **Unverified**

### Step 6 — Module 4 (Caregiver Dashboard): Ravi resolves it
Open `/caregiver`:

- [ ] **Needs Attention** tab shows both pill notes; the duplicate carries the
      red double-dose banner with the warning message text
- [ ] **Medication** tab shows exactly the two pill notes
- [ ] **Timeline** tab buckets them under Today; category chips filter correctly
- [ ] Ravi marks the 8:30 AM note **Confirmed** → badge flips to
      "Confirmed · Ravi" without a reload
- [ ] Ravi marks the duplicate **Incorrect** → relabels only (nothing is
      auto-deleted — that's the agreed behavior)
- [ ] Verify a failed request shows the "Try again" error (kill the API once
      to test, optional)

### Step 7 — Module 1: the trust loop closes
Patient asks again: "Did I take my medicine today?"

- [ ] Answer now reflects verification: took it once at 8:30 AM,
      **caregiver confirmed**; the duplicate is not presented as fact

### Step 8 — Module 3 + 4: consolidation (improve())
On the dashboard, click **Consolidate Today's Memories**:

- [ ] Returns ok + run_id; backend logs show `improve()` actually ran
- [ ] If pattern-surfacing is implemented: recurring pattern (e.g. repeated
      evening confusion) appears as bullets in the panel

### Step 9 — Module 4: surgical forget()
Ravi deletes the incorrect duplicate note from the dashboard:

- [ ] Confirm dialog → note disappears from all tabs
- [ ] The confirmed 8:30 AM note and the rest of the graph are untouched
      (re-check `/memory/graph`) — this is the "surgical" part
- [ ] Patient's "Did I take my medicine?" answer still works and is unchanged

### Step 10 — Full-wipe privacy path (optional, demo-dependent)
- [ ] "Delete all memories" for a throwaway test patient empties their
      dataset and only theirs (p_001 unaffected — per-patient isolation)

---

## After the walkthrough

- [ ] Run it once more, timed — this is the demo; it should take < 4 minutes
- [ ] Screenshot/log each Cognee call (remember, recall, improve, forget) for
      the judges — Japit's deliverable, but Member 4 owns the demo assets
- [ ] Sundowning Safe Mode check with Member 1 if it ships: does the patient
      UI actually switch after 5 PM?

**If every box above is checked, the four Cognee verbs are each demonstrated
by a visible product behavior — which is the judging story.**
