# Phase 3 — Knowledge (RAG) — Start Here

Phase 2 is complete in this repo. Phase 3 adds **document-grounded answers** with citations.

## Phase 2 recap (done)

- Tool-calling agent loop with policy tiers
- Notes, reminders, long-term memory (Postgres)
- Confirm-required flow: `POST /api/v1/actions/{id}/approve` and `/reject`
- Tool call audit logs in `tool_call_logs`
- Gateway proxies chat + action endpoints

## Phase 3 goals (from roadmap)

1. **Ingestion** — upload PDF/doc → extract → chunk → embed → store (start with **pgvector** on Neon or local Postgres)
2. **Retrieval agent** — multi-hop search until enough evidence
3. **Citations** — answers reference source chunks
4. **Upload API + status** — `processing` → `ready`

## Suggested first tasks tomorrow

1. Enable `pgvector` on your Neon project (or add extension migration `007_pgvector.sql`)
2. Implement `jarvis_ai/rag/pipeline.py` (currently stub):
   - `ingest_document(user_id, file_bytes, filename)`
   - `search_chunks(user_id, query, limit)`
3. Add tools: `search_documents` (safe), `ingest_document` (confirm-required)
4. Wire retrieval into orchestrator system prompt (like memory injection today)
5. Gateway route for `POST /api/v1/documents/upload` (multipart proxy)

## Key files to extend

| Area | Path |
|------|------|
| RAG stub | `python/jarvis_ai/rag/pipeline.py` |
| Migrations | `python/jarvis_ai/db/migrations/` |
| Tools | `python/jarvis_ai/tools/` |
| API | `python/jarvis_ai/api/main.py` |
| Spec | `specs.md` |

## Dev commands

```bash
make dev          # full stack
make test         # Go + Python tests
cd python && pytest tests/ -v
```
