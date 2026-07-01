# Claude Code Project Context

## Read First

1. AGENTS.md
2. The Full Project.md
3. TOOLING_AGENTS.md
4. .github/agents/*.agent.md (pick your role)

## Project Mission
Build a patient voice-memory app where voice notes become structured, caregiver-verifiable memory entries powered by Cognee memory operations.

## Team Roles

1. Patient App + Voice UX
2. Backend + STT + Structured Extraction
3. Cognee Memory Engine
4. Caregiver Dashboard + Safety + Demo Story

## Core MVP Loop
1. Record voice note
2. Transcribe
3. Extract structured memory
4. Store via remember()
5. Ask memory question
6. Recall via recall()
7. Show source + caregiver status

## Build Phases

1. Phase 1: Core loop working end-to-end
2. Phase 2: Alzheimer-specific safety and caregiver trust
3. Phase 3: Demo polish (timeline, consolidation trigger, forget flow)

## Role Routing
- Patient UI and calm UX: .github/agents/patient-voice-ux.agent.md
- Backend + STT + extraction: .github/agents/backend-stt-extraction.agent.md
- Cognee memory operations: .github/agents/cognee-memory-engine.agent.md
- Caregiver/safety/demo: .github/agents/caregiver-safety-demo.agent.md

## Constraints
- Keep language calm and reassuring for patients.
- Do not provide medical advice.
- Treat Cognee as first-class memory layer.
- Keep patient memory isolated by patient dataset.

## Runtime Commands
- npm run dev
- npm run dev:web
- npm run dev:api
- npm run dev:docker

## Cross-Tool Entry Files
- AGENTS.md
- The Full Project.md
- TOOLING_AGENTS.md
