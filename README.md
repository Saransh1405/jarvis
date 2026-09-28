# JARVIS

Personal AI assistant. **Go** runs the production edge (gateway, auth, proxy). **Python** runs the AI layer (orchestrator, tools, memory).

**Roadmap:** [`docs/JARVIS_Roadmap_v2.md`](docs/JARVIS_Roadmap_v2.md) (active). Legacy: [`docs/JARVIS_Roadmap.md`](docs/JARVIS_Roadmap.md).

## Status

**Phase 2 complete** — multi-user auth, persisted chat, tools/policy/audit, Postgres memory.

**Next:** Phase 3 **Reach** — deploy + web chat + 2-minute stranger onboarding. See [`docs/Phase3_Getting_Started.md`](docs/Phase3_Getting_Started.md).

## Structure

- `go/` — API gateway, user auth, MCP stub (Phase 4)
- `python/` — orchestrator, LLM, tools, memory, conversations
- `infra/` — Docker Compose
- `docs/` — roadmap, Phase 2 complete, specs in `specs.md`

## Quick start

```bash
cp .env.example .env
make dev
make test
```

Gateway: `http://localhost:8080` — signup at `POST /api/v1/auth/signup`, chat at `POST /api/v1/chat` with JWT.
