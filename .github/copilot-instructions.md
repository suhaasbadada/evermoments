# Copilot Instructions for Evermoments

Use capability ownership, not generic frontend/backend split.

## Read First
1. AGENTS.md
2. The Full Project.md
3. TOOLING_AGENTS.md
4. Relevant role agent in .github/agents/

## Project Mission
Build a patient voice-memory app where voice notes become structured, caregiver-verifiable memory entries powered by Cognee memory operations.

## Team Roles
1. Patient App + Voice UX
2. Backend + STT + Structured Extraction
3. Cognee Memory Engine
4. Caregiver Dashboard + Safety + Demo Story

## Core MVP Loop
1. Record voice note
2. Transcribe audio
3. Extract structured memory JSON
4. Store memory via remember()
5. Ask a memory question
6. Recall via recall()
7. Show source and caregiver status

## Build Phases
1. Phase 1 core loop: record -> transcribe -> extract -> remember; ask -> recall -> answer
2. Phase 2 Alzheimer-specific reliability: verification, gentle recall, medication duplicate warning, sundowning mode
3. Phase 3 demo polish: timeline, improve(), forget()

## Constraints
- Keep patient-facing copy simple and calm.
- Always preserve traceability: source, timestamp, caregiver status.
- Keep API contracts typed and stable.
- Keep Cognee usage explicit and demo-visible.
- Keep app DB and Cognee responsibilities separate.

## Role Routing
- .github/agents/patient-voice-ux.agent.md
- .github/agents/backend-stt-extraction.agent.md
- .github/agents/cognee-memory-engine.agent.md
- .github/agents/caregiver-safety-demo.agent.md

## Runtime Commands
- npm run dev
- npm run dev:web
- npm run dev:api
- npm run dev:docker
