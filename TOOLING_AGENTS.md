# Tooling Agent Entry Points

This file maps where contributors should look based on their coding tool.

## Read First
1. AGENTS.md
2. The Full Project.md
3. This file (TOOLING_AGENTS.md)

## Codex / Copilot in VS Code
- Shared project guidance: AGENTS.md
- Role agents: .github/agents/*.agent.md
- Copilot always-on instructions: .github/copilot-instructions.md

## Claude Code
- Claude project context: CLAUDE.md
- Shared project guidance: AGENTS.md
- Full spec: The Full Project.md
- Role definitions: .github/agents/*.agent.md

## Role Routing
- Patient UI and calm UX: .github/agents/patient-voice-ux.agent.md
- Backend + STT + extraction: .github/agents/backend-stt-extraction.agent.md
- Cognee memory operations: .github/agents/cognee-memory-engine.agent.md
- Caregiver/safety/demo: .github/agents/caregiver-safety-demo.agent.md

## Runtime Commands
- npm run dev
- npm run dev:web
- npm run dev:api
- npm run dev:docker

## Web App Scoped Notes
- apps/web/AGENTS.md
- apps/web/CLAUDE.md

## Suggested Team Workflow
1. Read AGENTS.md
2. Pick your role agent file
3. Implement only your owned capability
4. Keep contracts explicit for handoff
