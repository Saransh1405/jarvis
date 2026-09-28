# JARVIS — specs

Personal AI assistant. **Go** owns production edges (API gateway, auth, rate limits, proxy, future MCP server). **Python** owns the AI layer (orchestrator, LLM providers, tools, policy, notes/memory). Long-term plan: seven phases in `docs/JARVIS_Roadmap_v2.md`.

**Phase 2 complete.** Start **Phase 3 Reach** with `docs/Phase3_Getting_Started.md`. Roadmap: `docs/JARVIS_Roadmap_v2.md`.

---

## Product — what JARVIS is

JARVIS is a **personal AI assistant**: you talk to it in plain language, it remembers what matters to you, runs small tasks on your behalf, and **stops to ask** before it changes or saves something important. It is not a generic chat window — it is meant to stay useful across days and weeks, with your data under your deployment.

---

## Problems it solves

**Context lives in your head until it doesn’t.**  
You tell yourself you’ll renew a passport, follow up with a client, or remember a Wi‑Fi password — then life happens and the detail is gone. ChatGPT does not reliably remember *your* facts next week unless you manage that yourself. JARVIS is built to **store notes, reminders, and long-term facts** and surface them when you ask or when something is due.

**Too many apps, no one coordinator.**  
Calendar, notes, email, GitHub, and documents each have their own UI. You still do the glue work: check three places, copy text, decide what to do. JARVIS is the **single conversational layer** that can answer, recall, and (over time) connect to those systems so you describe the outcome once.

**AI that “just does things” is risky.**  
Sending email, creating events, or saving sensitive notes should not happen silently because a model guessed it was fine. JARVIS separates **read/search/calculate** (automatic) from **writes and reminders** (confirm first) and reserves the strictest tier for irreversible actions as integrations arrive.

**Generic assistants don’t know *you*.**  
Corporate chat products optimize for breadth, not your household, job, and habits. JARVIS is **yours**: one assistant profile, your memory, your integrations, your rules — suitable for a single owner today and controlled sharing later.

**You need answers from *your* information, not the whole internet.**  
For work and personal docs, “sound plausible” is not enough. The product direction includes **grounded answers from files you upload** (Phase 3), with citations — so “what does our policy say about X?” refers to your PDF, not a hallucination.

---

## Use cases

**Today (Phase 2 — chat + tools + memory)**

- **“Remember this for me.”** Save a note (e.g. insurance policy number, kid’s school gate code, project decision). Later: “What did I save about insurance?”
- **“Don’t let me forget.”** Set a reminder with a due time; JARVIS can include due reminders in context when you chat and list what’s coming up.
- **“What do you already know about me?”** Search stored memory facts so repeat explanations (“I’m vegetarian”, “my timezone is IST”) stick across sessions.
- **Quick help without opening another app.** Totals, splits, percentages via calculator while you stay in one conversation.
- **Controlled saves.** When saving a note or setting a reminder would change your data, JARVIS **asks you to approve** before it runs — so accidental model behavior does not silently write to your store.

**Coming next (product scenarios on the roadmap)**

- **“What does this document say?”** Upload a manual, contract, or design doc; ask questions and get answers tied to specific sections (Phase 3).
- **“What’s on tomorrow and what should I prep?”** Read calendar and tasks from real accounts; create or move events only after you confirm (Phase 4).
- **“Handle this project for me.”** Multi-step goals: research your notes, check schedule, draft or edit something in a repo — with a visible plan and approval before commits (Phase 5).
- **“I’m driving / holding my phone.”** Voice in and out; show a photo of a bill or receipt and have amounts or categories extracted with confirmation before saving (Phase 6).
- **“My friends use it too.”** Separate accounts, no shared memory, fair limits when several people use the same instance (Phase 7).

**Example day (target experience as phases land)**

Morning: “What reminders do I have today?” → afternoon: “Save that the plumber comes at 4” (approve save) → evening: “Search my memory for the plumber’s number” → later: “Summarize page 12 of the lease I uploaded” — one assistant, one thread of trust, your data persisted.

---

## Architecture

### Repository layout

- **`go/`** — HTTP gateway (`cmd/gateway`), middleware, reverse proxy to Python. MCP server stub for Phase 4 (`cmd/mcpserver`).
- **`python/`** — FastAPI, orchestrator + agent loop, LLM factory, tools, policy, Postgres persistence.
- **`infra/`** — Docker Compose (postgres, redis, `api`, `gateway`).
- **`.github/workflows/ci.yml`** — Go + Python tests on push/PR.
- **`.env.example`** — committed template; **`.env`** — secrets (never committed).

### Developer setup

```bash
cp .env.example .env
make dev          # Docker stack
make test         # unit tests
```

Python only: `cd python && source .venv/bin/activate && pip install -e . && pytest tests/ -v`

Set `DATABASE_URL` (Neon or local) for durable notes, reminders, memory, pending actions, and tool logs.

### Runtime — talking to JARVIS

**Entry:** Go gateway `http://localhost:8080` (proxies to Python).

**Auth:** `POST /api/v1/auth/login` (dev stub) → JWT → `Authorization: Bearer …`

**Chat:**

- `POST /api/v1/chat` or `POST /api/v1/chat/stream`
- Body: `{ "message": "...", "conversation_id": "optional" }`
- Gateway forwards **`X-User-ID`** for per-user data.

**Confirm-required actions (Phase 2.7):**

- Chat may return `pending_action` with `action_id`, `tool_name`, `arguments`.
- Stream may emit `{"type": "confirm_required", ...}` before tokens.
- `POST /api/v1/actions/{action_id}/approve` — runs tool and continues agent loop.
- `POST /api/v1/actions/{action_id}/reject` — cancels pending action.

### Tools (Phase 2) — policy tiers (Roadmap v2)

| Tool | Tier | v2 behavior |
|------|------|-------------|
| `calculator` | Safe | Auto-run |
| `get_note`, `list_reminders`, `search_memory`, `remember_fact` | Safe | Read/store memory; scoped by `user_id` |
| `save_note`, `set_reminder` | ConfirmRequired | Block until `POST /api/v1/actions/{id}/approve` (plain Yes/No UI in Phase 4 Reach) |

### Long-term memory (Phase 2 — Postgres)

- **Store:** `memory_facts` table (`PostgresMemoryStore`). Graphiti/Neo4j optional in Phase 5+ behind the same `MemoryStore` interface.
- **Write:** `remember_fact` tool, rule-based extraction after chat turns, `save_note` index (deduped).
- **Read:** Injected into system prompt + `search_memory` tool.

Confirm-tier tools **require** an authenticated `user_id` (via gateway JWT → `X-User-ID`). Executed tools are recorded in `tool_call_logs` with that `user_id`.

### Data (Postgres migrations on API startup)

- `notes`, `pending_actions`, `reminders`, `memory_facts`, `tool_call_logs`, `conversations`, `messages`
- Memory uses Postgres + `pg_trgm` (Graphiti/Neo4j optional upgrade later).

### Orchestrator behavior

1. Build system prompt with **due reminders** + **memory search** for the user message.
2. Agent loop: LLM → policy → tools → repeat.
3. Confirm-required tools create a `pending_actions` row and stop until approve.

### Not in scope yet (Phase 3+ Reach / Phase 6 depth)

- RAG / document upload (`jarvis_ai/rag/pipeline.py` — Phase 6 pilot-driven, not Phase 3 Reach)
- Chat web UI (Phase 3 Reach)
- MCP + OAuth integrations (Phase 4)

### Request path

```
Client → Go Gateway (:8080) → Python FastAPI (:8000)
         JWT, rate limit          Orchestrator → LLM → policy → tools
                                        ↓
                                   Postgres (Neon)
```
