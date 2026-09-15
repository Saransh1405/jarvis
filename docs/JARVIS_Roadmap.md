# JARVIS — Production Roadmap (7 Phases)

**Ground rule for every phase:** if you can't deploy it, hit it from your phone, and show it to a stranger, the phase isn't done. No phase is "conceptually complete" — it's either live or it isn't.

**Cross-cutting rule (not a phase, a habit):** starting from Phase 1, every phase ships with:
- Dockerized services + docker-compose (later: k8s manifests)
- CI (lint, test, build) on every push
- Structured logging + basic tracing (even if it's just request-id + latency in Postgres)
- One environment variable file pattern (`.env.example` committed, `.env` never committed)
- A `/health` and `/ready` endpoint on every service

Security and observability are **not Phase 7 anymore** — they're baked into Phase 1 and grow with each phase. That's the difference between a portfolio project and something production-grade.

---

## Phase Map

| # | Phase | Core Question It Answers |
|---|-------|---------------------------|
| 1 | Foundation & Conversational Core | Can I talk to JARVIS, live, on a real URL? |
| 2 | Tools + Memory | Can JARVIS *do* small things and *remember* them? |
| 3 | Knowledge (RAG) | Can JARVIS answer from *my* documents? |
| 4 | MCP + Real Integrations | Can JARVIS touch my actual Gmail/Calendar/GitHub? |
| 5 | Planning + Multi-Agent | Can I give it a goal and it figures out the steps? |
| 6 | Multimodal + Voice + Computer Use | Can I talk to it and show it things, and can it act on a screen? |
| 7 | Hardening & Scale | Can other people use this safely, at the same time, without me babysitting it? |

---

## Phase 1 — Foundation & Conversational Core

**Ships:** A real chat app, at a real domain, with streaming responses, that you can send friends a link to.

**Build:**
- Go API Gateway (auth stub, rate limiting middleware, WebSocket/SSE streaming passthrough)
- Python AI service (LLM call, streaming, conversation persistence)
- Postgres (conversations, messages) + Redis (session/rate-limit state)
- Minimal web frontend (or just a clean HTML page — doesn't need to be fancy yet)
- Deploy: Docker Compose → a real host (Railway/Fly.io/Hetzner+Coolify are the easiest for a solo side project; move to k8s only in Phase 7 if you actually need it)
- CI: GitHub Actions running tests + build on every PR
- Observability: request logging with latency + token usage per call, stored in Postgres

**Production-ready checklist:**
- [ ] Live HTTPS domain
- [ ] Streaming works under real network conditions (not just localhost)
- [ ] Survives a service restart without losing conversation history
- [ ] Basic uptime monitoring (even just a free UptimeRobot ping)

**Demo:** You text a friend a link. They chat with JARVIS. It streams. It remembers the conversation if they refresh.

```
                              INTERNET
                                 │
                            HTTPS (TLS)
                                 │
                       ┌─────────────────┐
                       │   Go API Gateway │  ← rate limiting, auth stub,
                       │   (WS/SSE proxy) │    request logging
                       └────────┬────────┘
                                │  internal HTTP
                       ┌────────▼────────┐
                       │  Python AI Svc   │  ← LLM call, streaming,
                       │  (Orchestrator)  │    prompt assembly
                       └────────┬────────┘
                                │
                         ┌──────┴──────┐
                         ▼             ▼
                    ┌─────────┐   ┌─────────┐
                    │ Postgres │   │  Redis  │
                    │ (convos, │   │(sessions,│
                    │ messages)│   │rate-limit)│
                    └─────────┘   └─────────┘
                                │
                                ▼
                          LLM Provider API

        CI: GitHub Actions → build/test/lint on every push
        Monitoring: /health, /ready, uptime ping, request-latency log
```

---

## Phase 2 — Tools + Memory

**Ships:** JARVIS can take small actions (calculator, notes, reminders) and *remember things across sessions* — this is where memory tech and the permission layer both enter, together, because "JARVIS can act" and "JARVIS should ask before acting" are the same feature.

**Build:**
- Tool-calling loop (LLM → tool decision → execute → result → LLM)
- Starter tools: `calculator`, `save_note`, `get_note`, `set_reminder`
- **Permission tiers introduced here, not later:**
  - Safe (auto-run): read/search/calculate
  - Confirm-required: anything that writes/modifies
  - Always-confirm: anything irreversible (delete, send, purchase) — not reachable yet, but the policy engine exists now so it's not bolted on later
- **Memory layer — pick one deliberately:**

| | **Graphiti** | **Supermemory** |
|---|---|---|
| What it is | Open-source temporal knowledge graph (built on Neo4j) | Hosted memory API |
| You run | Neo4j + Graphiti service yourself | Nothing — it's a managed API |
| Best for | Learning graph-based memory internals, full control, self-hosted "production" story | Shipping fast, less infra to own |
| Cost | Your own DB hosting | Usage-based API pricing |
| Fits your "learn by building" goal | Very well — you own the whole pipeline | Less — it's someone else's black box |

  → **My suggestion given your stated goal (learn + own the stack):** start with **Graphiti**. You already have Postgres/Redis in your infra; adding Neo4j is one more container, and you get to actually understand temporal knowledge graphs instead of calling an API. Keep Supermemory in your back pocket as a fallback if Graphiti's ops overhead slows you down.

**Production-ready checklist:**
- [ ] Tool calls are logged (what was called, with what args, what it returned)
- [ ] Confirm-required actions actually pause and wait for user approval in the UI
- [ ] Memory persists across container restarts and across days
- [ ] You can ask "what did I tell you last week about X" and get a correct answer

**Demo:** "Remind me to renew my passport, and save a note that my passport number is X." Days later: "What did I ask you to remind me about?" — correct answer, from cold memory, not conversation history.

```
                    USER MESSAGE
                         │
                         ▼
                 ┌───────────────┐
                 │  Python Agent  │
                 │  (LLM + loop)  │
                 └───────┬───────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐┌─────────┐┌───────────┐
        │  Policy   ││  Tools   ││  Memory   │
        │  Engine   ││ Registry ││  Layer    │
        │(safe /    ││(calc,    ││ (Graphiti │
        │ confirm / ││ notes,   ││  + Neo4j) │
        │ always)   ││ reminder)││           │
        └────┬─────┘└────┬────┘└─────┬─────┘
             │            │            │
     "needs confirm?" → UI approval prompt
             │            │            │
             ▼            ▼            ▼
                    Result → back to LLM
                         │
                         ▼
                   Response to user
```

---

## Phase 3 — Knowledge (RAG)

**Ships:** Upload a PDF/doc, ask questions about it, get grounded answers — with agentic multi-hop retrieval baked in from the start (no throwaway "simple RAG" you rebuild later).

**Build:**
- Ingestion pipeline: extract → chunk → embed → store (pgvector is fine — one less service to run; move to a dedicated vector DB only if you outgrow it)
- Retrieval agent: decides what to search, evaluates if it has enough evidence, re-searches if not, then answers with citations back to source chunks
- File upload UI + status ("processing", "ready")

**Production-ready checklist:**
- [ ] Handles a real 50-page PDF without falling over
- [ ] Answers cite which document/section they came from
- [ ] Re-querying works (agent visibly searches more than once when the first pass is thin)
- [ ] Old documents can be deleted and their vectors actually go away (data hygiene, not just a UI hide)

**Demo:** Upload your JARVIS design doc itself. Ask "which phase introduces the permission engine and why is it not in phase 7?" — correct, cited answer.

```
      FILE UPLOAD                          QUESTION
           │                                   │
           ▼                                   ▼
   ┌───────────────┐                  ┌────────────────┐
   │  Ingestion Job │                  │ Retrieval Agent │
   │ extract→chunk  │                  │  (multi-hop)    │
   │  →embed        │                  └────────┬───────┘
   └───────┬───────┘                            │
           ▼                          ┌──────────┴──────────┐
   ┌───────────────┐                  ▼                     ▼
   │ Postgres +     │◄─────── search ─┤ enough evidence? ────► answer
   │ pgvector       │                  │  no → search again   │  with
   │ (chunks + meta)│                  └──────────────────────┘  citations
   └───────────────┘
```

---

## Phase 4 — MCP + Real Integrations

**Ships:** JARVIS as an MCP server, connected to at least one real external account (start with GitHub or Calendar — Gmail last, it's the highest-stakes one to get permission handling right on).

**Build:**
- Your own **JARVIS Personal MCP Server** (Go, since MCP servers are infra, not AI logic) exposing `search_memory`, `save_note`, `get_tasks`, etc.
- OAuth flow for at least one real service
- Permission tiers from Phase 2 now actually gate real-world actions: reading a calendar = safe; creating an event = confirm-required; sending an email = always-confirm

**Production-ready checklist:**
- [ ] OAuth tokens stored encrypted, refreshed automatically
- [ ] An external MCP client (e.g. Claude Desktop) can discover and call your server's tools
- [ ] A destructive/sensitive action is demonstrably blocked without explicit confirmation
- [ ] Revoking access in the third-party account (e.g. Google) actually breaks the integration cleanly (no silent failure loop)

**Demo:** "What's on my calendar tomorrow, and do I have any open GitHub issues assigned to me?" — real data, real accounts. Then: "Create a calendar event for Friday at 3pm" — JARVIS asks for confirmation first.

```
                 EXTERNAL MCP CLIENT (e.g. Claude Desktop)
                                │
                                ▼
                    ┌───────────────────────┐
                    │  JARVIS MCP Server (Go) │
                    │  search_memory()        │
                    │  get_tasks()             │
                    │  create_event()          │
                    └───────────┬─────────────┘
                                │
                   ┌────────────┼────────────┐
                   ▼            ▼             ▼
             Policy Engine   OAuth Store   Orchestrator
             (from Phase 2)  (encrypted)   (Python)
                   │            │
                   ▼            ▼
             confirm-required?  Google Calendar / GitHub API
                   │
                   ▼
              UI approval → execute → log
```

---

## Phase 5 — Planning + Multi-Agent Orchestration

**Ships:** Give JARVIS a goal, not a command, and it breaks it into steps, delegates to specialized sub-agents, and executes — including a basic coding agent against a real repo.

**Build:**
- Planner: goal → task list → execution → observation → re-plan if needed
- Sub-agents: Researcher (uses Phase 3 RAG), Coder (reads/edits a repo, runs tests, shows diff, asks permission before commit — this is where Phase 12 from the old plan lives now), Personal Agent (uses Phase 4 integrations)
- Orchestrator routes tasks to the right sub-agent and merges results

**Production-ready checklist:**
- [ ] A multi-step goal visibly produces a plan *before* execution starts (not just a black box)
- [ ] You can interrupt/cancel a running plan
- [ ] The coding agent shows a diff and waits for approval before committing — no exceptions
- [ ] Failure of one sub-agent doesn't crash the whole run; it surfaces as a clear partial result

**Demo:** "Check my calendar, find my Golang notes on interfaces, and add a small doc comment to the `UserService` struct in my repo explaining what it does." — plan shown, steps executed across three sub-agents, diff shown, approval requested.

```
                        GOAL: "..."
                             │
                             ▼
                     ┌───────────────┐
                     │    Planner     │  → produces visible task list
                     └───────┬───────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                    ▼
   ┌───────────┐      ┌───────────┐        ┌─────────────┐
   │ Researcher │      │   Coder    │        │  Personal    │
   │  Agent     │      │   Agent    │        │  Agent       │
   │(Phase 3 RAG)│      │(repo, diff,│        │(Phase 4 MCP  │
   │            │      │ tests,     │        │ integrations)│
   │            │      │ approval)  │        │              │
   └─────┬─────┘      └─────┬─────┘        └──────┬───────┘
         └───────────────────┼──────────────────────┘
                             ▼
                    Merge results → user
                             │
                             ▼
                     Cancel/interrupt hook (any point)
```

---

## Phase 6 — Multimodal + Voice + Computer Use

**Ships:** You can talk to JARVIS out loud, show it a photo/screenshot/bill, and — capstone feature — it can drive a browser to complete a task while showing you what it's doing.

**Build:**
- STT (speech-to-text) in, TTS (text-to-speech) out
- Vision: image/document understanding wired into the existing tool + agent loop (a bill photo → extract amount → categorize → confirm → save, using Phase 2's memory and confirmation flow — nothing new architecturally, just a new input modality)
- Computer-use loop: goal → screenshot → vision model reasons → action → screenshot → repeat, with every step logged and a live view for the user to watch

**Production-ready checklist:**
- [ ] Voice round-trip works with real background noise / normal speech, not just silence
- [ ] A photo of a real bill gets correctly extracted and categorized
- [ ] Computer-use actions are sandboxed (isolated browser context, not your real logged-in session) and every action is logged and replayable
- [ ] Computer-use always confirms before any action that touches a real account (matches Phase 2's "always-confirm" tier)

**Demo:** Talk to JARVIS: "Book me the cheapest flight to Delhi next Friday, show me before you do anything." It narrates its plan, opens a sandboxed browser, shows you screenshots as it goes, and stops for confirmation before checkout.

```
   MIC ──STT──►┐                          Screenshot ◄────┐
                │                                          │
   IMAGE ───────┤                                          │
                ▼                                          │
        ┌───────────────┐                         ┌────────────────┐
        │  Multimodal    │                         │ Computer-Use    │
        │  Input Handler │──── goal ──────────────►│ Agent (sandboxed│
        │ (vision + text)│                         │ browser context)│
        └───────┬───────┘                         └────────┬────────┘
                │                                            │
                ▼                                            ▼
        Existing Tool/Agent Loop                    Action log + live
        (Phase 2/4/5, unchanged)                    view for user
                │                                            │
                ▼                                            ▼
              TTS out                              Confirm before
                                                     account-touching step
```

---

## Phase 7 — Hardening & Scale

**Ships:** JARVIS as something *other people* can sign up for and use concurrently, safely, without you manually watching it.

**Build:**
- Real auth (not the Phase 1 stub) — multi-user, proper session/token handling
- Secrets management (move out of `.env` into a vault — Doppler/1Password/cloud secrets manager)
- Rate limiting per user, queues for long-running agent tasks (so one user's slow coding-agent run doesn't block another user's chat)
- Full eval suite: automated tests for tool selection accuracy, hallucination rate, latency, cost per run
- Move to k8s (or managed equivalent) only now, once you actually have multi-user load that justifies it
- Backups (Postgres + Neo4j) and a documented restore procedure you've actually tested

**Production-ready checklist:**
- [ ] Two different users can use JARVIS at the same time without seeing each other's data
- [ ] A restore-from-backup drill has actually been run, not just scheduled
- [ ] You have dashboards for cost, latency, and error rate — not just logs you'd have to grep
- [ ] Load test survives at least 10 concurrent users doing real multi-step tasks

**Demo:** Invite 5 friends. They sign up, chat, use tools, upload docs — simultaneously — with no cross-contamination and a dashboard you can point to and say "here's what it cost and how fast it was."

```
                         USERS (multiple)
                                │
                        ┌───────┴───────┐
                        ▼               ▼
                  Auth/Session      Rate Limiter
                  (real, multi-user)  (per-user)
                        │               │
                        └───────┬───────┘
                                ▼
                    ┌───────────────────┐
                    │   Queue (per-task)  │  ← long agent runs don't
                    └─────────┬─────────┘     block other users
                              ▼
                  All prior phases' services
                  (now horizontally scalable)
                              │
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
             Postgres    Neo4j/Graphiti  Redis
             (backed up) (backed up)   (cache/queue)
                              │
                              ▼
                  Dashboards: cost / latency / errors
                  Vault: secrets (not .env anymore)
```

---

## Suggested Order of Attack

Do them strictly in order — each phase's "confirm-required" and permission machinery (introduced in Phase 2) is load-bearing for Phases 4, 5, and 6. Skipping ahead means retrofitting security later, which is exactly what this restructuring was meant to avoid.

If you want, I can turn any single phase into a concrete week-by-week task breakdown, or start scaffolding Phase 1's repo structure and docker-compose right now.
