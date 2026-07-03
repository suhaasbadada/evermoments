# Caregiver Dashboard (Member 4)

Owner: Member 4. Consumes Module 3's (Japit, Cognee Memory Engine) `/memory/*`
contract. Does not talk to Cognee directly — everything goes through
`lib/memory/client.ts`.

## What's built

```
src/types/memory.ts                        contract types (MemoryResult, VerificationStatus, EventType, MemoryClient)
src/lib/memory/
  constants.ts                             DEFAULT_PATIENT_ID = "p_001" (matches Japit's seed_dummy_data.py)
  format.ts                                formatRecordedAt() -> "Today, 4:30 PM" / "Yesterday, ..." / "Jun 28, ..."
  labels.ts                                verification status labels, badge colors, the 4 caregiver action buttons
  mock.ts                                  fake in-memory backend, satisfies MemoryClient, seeded with a double-dose scenario
  api.ts                                   real backend, satisfies MemoryClient, calls Japit's /memory/* endpoints
  client.ts                                exports `memoryClient` = mock or real, switched by NEXT_PUBLIC_USE_MOCK_MEMORY
  insights.ts                              computeInsights(): frequency signals over the memory list (see Patterns & Signals)
src/components/caregiver/
  caregiver-dashboard.tsx                  top-level client component: fetch, tab state, verify/delete handlers
  tab-bar.tsx                              Needs Attention / All Memories / Medication / Timeline
  memory-card.tsx                          one memory: fact, source, timestamp, verification badge, warning banner, actions
  verification-actions.tsx                 Confirmed / Needs Checking / Incorrect / Safety Critical buttons
  consolidate-panel.tsx                    "Consolidate Today's Memories" button -> improve(), shows surfaced patterns
  insights-panel.tsx                       "Patterns & Signals" card rendering computeInsights() output
  timeline-view.tsx                        Timeline tab: Today/Yesterday/This Week/Earlier buckets + category chips
src/app/caregiver/page.tsx                 route: /caregiver
```

Verified: `tsc --noEmit` clean, `next build` clean, dev server serves `/caregiver`
with no console errors.

## How to test right now (no other member needed)

`memoryClient` defaults to the mock backend (`NEXT_PUBLIC_USE_MOCK_MEMORY` unset
or not `"false"`). Run `npm run dev:web` (or `npm run dev` from repo root) and
open `/caregiver`.

Mock fixture (patient `p_001`, mirrors Japit's own seed data):
- wallet note (unverified)
- blue pill @ 8:30 AM (unverified)
- blue pill @ 10:45 AM (**safety_critical**, carries the double-dose warning message)
- Ravi's visit yesterday (confirmed)
- an appointment 3 days ago (unverified)
- two "confused after dinner" observations (4 and 10 days ago) — the recurring
  pattern Japit's improve() demo is meant to surface, and they populate the
  timeline's This Week / Earlier buckets

Walkthrough:
1. "Needs Attention" tab shows the 3 unresolved/flagged notes, including the red double-dose banner.
2. Click "Confirmed" / "Incorrect" on a note — badge updates instantly, card moves between tabs live.
3. "Medication" tab shows both pill notes.
4. "Timeline" tab groups everything under Today / Yesterday / This Week / Earlier,
   with category chips (People, Places & Objects, Medication, Appointments,
   Observations) filtering by event_type.
5. "Consolidate Today's Memories" — spinner, then a mocked pattern bullet appears.
6. Delete a card — confirm dialog, then it's gone (mock array mutation, not persisted across reload).

## Decisions locked in this session

- Verification actions are exactly **4**: Confirmed, Needs Checking, Incorrect,
  Safety Critical. "Duplicate" (from the original 5-button mockup in Plan.docx)
  was dropped — Japit's `verification.status` enum (§6.1) never had it, and the
  team agreed "Incorrect" covers that case.
- Marking something "Incorrect" only relabels it — no auto-delete, no auto
  `forget()`, no cascading effect on `improve()`. Purely a caregiver-visible flag.
- Spaced/gentle recall UI is **on hold** — not built, not scoped in this pass.
- Tabs: **Needs Attention** (unverified + needs_check + safety_critical) / **All** /
  **Medication** / **Timeline**.
- Timeline lives as a fourth tab, not a separate route — keeps the dashboard a
  single simple screen. Filtering is client-side over the already-fetched list
  (the /memory/list date/event_type filters exist in the contract and mock for
  when server-side filtering becomes worth it).
- **Patterns & Signals** (behavior analysis, lightweight): `computeInsights()`
  counts frequency signals over a 10-day window, from two labeled sources —
  patient recordings (same fact recorded on 2+ distinct days, duplicate
  medication flags) and caregiver responses (notes marked incorrect, open
  safety-critical notes). The caregiver-response signals measure the gap
  between what the patient believes and what actually happened (the
  anosognosia angle). Client-side counting only — complements Japit's
  improve() graph-derived patterns, doesn't duplicate them. Framed on the
  card as "communication summary for caregivers — not a medical assessment"
  (per AIHangover §7: never pitch as detection/diagnosis).

## What's still open / pending

1. **`/memory/list` endpoint doesn't exist yet.** Japit agreed to add it:
   ```
   POST /memory/list
   { patient_id, filters: { event_type?, verification_status?, date_from?, date_to? },
     sort?: "recorded_at_desc", limit? }
   -> MemoryAnswer.results[]
   ```
   `lib/memory/api.ts` is already written against this exact shape. Nothing to
   change on our side once it's live — just flip the env flag (see below).

2. **`/memory/consolidate` response shape beyond `{ok, run_id}` is unconfirmed.**
   `consolidate-panel.tsx` expects an optional `patterns: string[]` field and
   renders it as bullets. If Japit's real response uses a different key or
   shape, the panel will silently show zero bullets (`result.patterns ?? []`
   swallows the mismatch) instead of erroring — worth explicitly confirming
   the field name with him, not assuming.

3. **Per-item warnings aren't in the list contract.** The double-dose message
   text is only guaranteed to exist once, in the ingest response (per §6.2).
   `MemoryResult.warning` is an optional field we added speculatively so the
   UI already knows how to render it — but confirm with Japit whether
   `/memory/list` will actually carry it through on safety_critical items, or
   whether the dashboard only gets the bare `verification_status` badge with
   no explanatory message.

4. **No automated tests.** Everything above was verified manually + via
   `tsc`/`next build`. No test runner is configured in `apps/web` yet
   (`package.json` only has a `lint` script). Worth adding basic tests for
   `lib/memory/mock.ts`'s filtering/sorting and timeline-view's bucketing logic
   if time allows — that's the real business logic in this module.

5. **Demo script / pitch deck not started** — Member 4 deliverable, owned here.

## Integration checklist (mock -> real)

- [ ] Japit's `/memory/list`, `/memory/verify`, `/memory/consolidate`,
      `DELETE /memory` are live and reachable from `apps/api`.
- [ ] Confirm `/memory/consolidate` response field name for surfaced patterns.
- [ ] Confirm whether `/memory/list` items carry a `warning` object on
      safety_critical notes.
- [ ] Member 2's real pipeline is producing `MemoryEvent`s for patient `p_001`
      (or whatever patient ID the demo uses) so the dashboard has real data,
      not just Japit's seed script.
- [ ] Set `NEXT_PUBLIC_USE_MOCK_MEMORY=false` in `apps/web/.env.local`.
- [ ] Re-run the same manual walkthrough above against the real backend.
