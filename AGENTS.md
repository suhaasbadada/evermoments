# Evermoments Agent Guide

This repository is organized around product capabilities, not generic frontend/backend slices.

## Read First

1. AGENTS.md
2. The Full Project.md
3. TOOLING_AGENTS.md
4. Relevant role agent in .github/agents/

## Project Mission
Build a patient voice-memory app where each voice note becomes a structured, caregiver-verifiable memory graph entry. The system uses Cognee memory operations to support recall, consolidation, and deletion.

## Team Roles

1. Patient App + Voice UX
2. Backend + STT + Structured Extraction
3. Cognee Memory Engine
4. Caregiver Dashboard + Safety + Demo Story

## Core MVP Loop

1. Record voice note
2. Transcribe audio
3. Extract structured memory JSON
4. Store memory via Cognee remember()
5. Ask a memory question
6. Recall via Cognee recall()
7. Show patient-friendly answer with source and caregiver status

## Required Cognee Story for Demo

- remember(): persist structured memory
- recall(): retrieve relevant memory with temporal context
- improve(): consolidate fragmented daily memories
- forget(): remove a memory or patient memory set

## Build Phases

1. Phase 1: Core loop working end-to-end
2. Phase 2: Alzheimer-specific safety and caregiver trust
3. Phase 3: Demo polish (timeline, consolidation trigger, forget flow)

## Constraints

- Keep language patient-friendly and calm.
- Do not present medication advice as medical advice.
- Treat Cognee as first-class memory layer, not an afterthought.
- Keep patient memory isolated by patient dataset.

## Agent Files

Use the role-specific custom agents in .github/agents for implementation tasks:

- patient-voice-ux.agent.md
- backend-stt-extraction.agent.md
- cognee-memory-engine.agent.md
- caregiver-safety-demo.agent.md

## Cross-Tool Entry Files

- Codex/Copilot: AGENTS.md, .github/agents/*.agent.md, .github/copilot-instructions.md
- Claude Code: CLAUDE.md, AGENTS.md, The Full Project.md
- Tool map: TOOLING_AGENTS.md

## Runtime Commands

- npm run dev
- npm run dev:web
- npm run dev:api
- npm run dev:docker
