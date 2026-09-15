# JARVIS

Personal AI assistant. Go handles infra/production concerns (API gateway, MCP server,
databases). Python handles the AI layer (orchestration, agents, memory, RAG).

See `docs/JARVIS_Roadmap.md` for the 7-phase build plan.

## Structure
- `go/` — API gateway, MCP server, shared Go infra packages
- `python/` — orchestrator, agents, tools, memory, RAG
- `shared/` — OpenAPI contract + JSON schemas between the two services
- `infra/` — docker-compose, k8s (Phase 7), terraform (Phase 7)
- `docs/` — roadmap, architecture diagrams, ADRs

## Status
Scaffolding only. No functioning code yet — see TODO comments per file.
