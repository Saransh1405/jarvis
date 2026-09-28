# Phase 3 — Reach — Start Here

Phase 2 is complete per [`docs/JARVIS_Roadmap_v2.md`](JARVIS_Roadmap_v2.md). Phase 3 is **Reach**: a real URL, signup → first useful reply in under two minutes, no hand-holding.

## Phase 2 recap (done)

- Real signup/login on gateway; `user_id` on every request
- Postgres chat history (`conversations`, `messages`)
- Tools, policy tiers, confirm API, `tool_call_logs`
- Long-term memory (`memory_facts`, `remember_fact`, chat extraction) — Postgres, Graphiti deferred

## Phase 3 goals (Reach)

1. **Hosted deploy** — Fly.io / Railway + HTTPS
2. **One channel** — minimal web chat UI (fastest path)
3. **2-minute onboarding** — signup → first message → helpful reply
4. **CI deploy gate** — extend [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
5. **Uptime** — monitor `GET /health`

## Not Phase 3

- Document RAG / pgvector → **Phase 6** (pilot-driven). See stub `python/jarvis_ai/rag/pipeline.py`.

## Suggested first tasks

1. Static or SPA chat page: login, stream chat, show `conversation_id`
2. Production env + managed Postgres + secrets
3. Wire CI to deploy on green tests
4. Send a non-technical friend the link with zero instructions; time to first useful reply

## Dev commands

```bash
make dev
make test
cd python && pytest tests/ -v
```
