# The Full Project

## Read First

1. AGENTS.md
2. TOOLING_AGENTS.md
3. CLAUDE.md or .github/copilot-instructions.md (based on your tool)
4. Relevant role file in .github/agents/

## Vision
Evermoments is a patient voice-memory app where every voice note becomes a structured, caregiver-verifiable memory entry powered by Cognee memory operations.

Patients can ask practical daily questions such as:
- Where is my wallet?
- Who visited me yesterday?
- Did I take medicine today?

The app responds using prior voice notes, time context, people, places, routines, and caregiver confirmations.

## MVP Definition
A complete MVP means the following loop works reliably:

1. Patient records a voice note.
2. Audio is transcribed.
3. Backend extracts structured memory JSON.
4. Memory is persisted through Cognee remember().
5. Patient asks a question.
6. Cognee recall() returns relevant memory.
7. App shows a simple answer with source and caregiver status.

## Core Product Surfaces

### 1) Patient App
- Record Memory
- Ask My Memory
- Today’s Important Memories
- Gentle Recall Practice
- Sundowning Safe Mode (calmer UI in evening)

### 2) Backend Memory Pipeline
- Voice note ingestion endpoint
- Speech-to-text
- Structured entity/time extraction
- Memory classification
- Persistence in app database

### 3) Cognee Memory Engine
- remember(): store structured memory
- recall(): answer memory questions
- improve(): consolidate daily memory fragments
- forget(): delete memory for privacy/user control

### 4) Caregiver Dashboard and Safety
- Recent memories and pending verification
- Verification state management
- Medication duplicate warning support
- Memory timeline

## Team Split (4 Members)

### Member 1: Patient App + Voice UX
Owns:
- Patient homepage
- Voice recording flow
- Ask-memory screen
- Answer card UI
- Sundowning mode behavior

Deliverable:
Patient can record, ask, and receive calm, source-aware answers.

### Member 2: Backend + STT + Extraction
Owns:
- FastAPI endpoints
- Speech-to-text integration
- Structured extraction and classification
- Database schema and persistence

Deliverable:
Voice note converts to stable structured memory payload.

### Member 3: Cognee Cloud + Memory Graph + Recall
Owns:
- Cognee Cloud connection
- remember(), recall(), improve(), forget()
- Per-patient dataset isolation
- Temporal recall behavior

Deliverable:
Cognee operations are running and demo-visible, not hidden.

### Member 4: Caregiver Dashboard + Safety + Demo
Owns:
- Caregiver verification flows
- Safety and duplicate-medication UX
- Timeline view
- End-to-end demo script and pitch flow

Deliverable:
Caregiver trust and safety layer is demo-ready.

## Recommended Ownership Matrix

- Patient UI: Member 1 primary
- Voice recording: Member 1 + Member 2
- STT: Member 2 primary
- Structured extraction: Member 2 primary
- Cognee remember/recall/improve/forget: Member 3 primary
- Caregiver dashboard: Member 4 primary
- Verification workflow: Member 4 primary
- Demo story: Member 4 primary

## Build Order

### Phase 1: Core Working Loop
Must complete first:
- Record voice -> transcribe -> extract -> remember()
- Ask memory -> recall() -> answer

### Phase 2: Alzheimer-Specific Reliability
Add:
- Caregiver verification
- Gentle spaced recall
- Medication duplicate warning
- Sundowning safe mode

### Phase 3: Demo-Ready Polish
Add:
- Timeline view
- Memory consolidation button (improve())
- Delete memory flow (forget())
- Optional simple graph visualization

## Feature Priority

### Must-have
1. Voice note recording
2. Transcription
3. Structured memory card
4. Cognee remember()
5. Ask-memory via recall()
6. Caregiver verification

### Should-have
1. Timeline view
2. Medication duplicate warning
3. Gentle spaced recall prompt
4. Source and confidence labels

### Nice-to-have
1. Music memory cue
2. Voice wellness timeline
3. Full graph visualization
4. Export memory book

## Architecture (Practical)

- Next.js web app for patient and caregiver UI
- FastAPI service for ingestion, extraction, and app APIs
- SQL database for transactional app data and verification status
- Cognee as persistent graph-vector memory layer for recall and consolidation

## Sample Structured Memory Payload

```json
{
  "memory_type": "object_location",
  "transcript": "I kept my wallet near the TV.",
  "entities": {
    "object": "wallet",
    "place": "near the TV"
  },
  "time_reference": "today",
  "caregiver_status": "unverified"
}
```

## Demo Script (Judge-Facing)

1. Patient records: "I kept my wallet near the TV."
2. App transcribes and extracts structured memory.
3. Cognee remember() stores it.
4. Patient asks: "Where is my wallet?"
5. Cognee recall() returns the answer.
6. Caregiver marks memory as confirmed.
7. Patient asks again and sees confirmed status.
8. App runs improve() to consolidate daily memories.
9. User deletes memory through forget().

## Judging Angle
The differentiator is not simple note storage. The differentiator is converting daily voice fragments into persistent, caregiver-verifiable memory intelligence using Cognee.
