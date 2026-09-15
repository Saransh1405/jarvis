# Phase 2 — Python Learning Path (Sub-phases)

**Audience:** New to Python, comfortable with Go from Phase 1.  
**Assumption:** Go gateway stays as-is for Phase 2. Python owns tools, policy, memory, and the agent loop.

**Phase 2 goal:** JARVIS can *act* (tools), *ask before risky actions* (policy), and *remember* across sessions (memory).

---

## How to use this doc

- Complete **one sub-phase at a time**. Don’t skip ahead.
- Each sub-phase ends with a **“You know it works when…”** check.
- Use `LLM_PROVIDER=stub` until you have API keys — stub is enough for 2.1–2.6.
- Run tests after each sub-phase: `cd python && pytest tests/ -v`

---

## Go vs Python in Phase 2

| Layer | Phase 2 work |
|-------|----------------|
| **Go gateway** | Mostly done — auth, proxy, rate limit. Optional later: policy HTTP API if Python calls `POLICY_SERVICE_URL`. |
| **Python** | All new Phase 2 logic lives here. |

You do **not** need to touch Go until sub-phase 2.7+ (if you centralize policy on the gateway).

---

## Sub-phase map (overview)

| # | Name | ~Time | Python concepts you learn |
|---|------|-------|---------------------------|
| 2.1 | Read the codebase | 1 session | imports, packages, async basics |
| 2.2 | Tool registry + calculator | 1–2 sessions | classes, dicts, typing |
| 2.3 | Agent loop (no LLM tools yet) | 1 session | `async`/`await`, control flow |
| 2.4 | LLM tool calling | 2 sessions | provider APIs, JSON schemas |
| 2.5 | Policy tiers | 1 session | enums, branching |
| 2.6 | Notes + Postgres | 2 sessions | SQL, async DB (or sync first) |
| 2.7 | Confirm-required flow | 2 sessions | API design, state machine |
| 2.8 | Reminders | 1–2 sessions | scheduling basics |
| 2.9 | Memory (Graphiti) | 3+ sessions | external service, Docker |

---

## 2.1 — Read the codebase (no new features)

**Goal:** Understand where Phase 2 code will live before writing it.

**Read these files in order:**

1. `jarvis_ai/config/settings.py` — env vars (`Settings`)
2. `jarvis_ai/api/main.py` — HTTP routes (FastAPI)
3. `jarvis_ai/orchestrator/orchestrator.py` — chat logic today
4. `jarvis_ai/llm/base.py` + `factory.py` — provider switch
5. `jarvis_ai/tools/registry.py` — empty stub (your future work)
6. `jarvis_ai/policy/policy.py` — `Tier` enum stub
7. `jarvis_ai/memory/store.py` — empty stub

**Python concepts:**

- `from jarvis_ai.X import Y` — how packages connect (like Go imports)
- `@app.post(...)` — route decorator
- `async def` — function that can pause (like goroutines + channels, but simpler syntax)
- `BaseModel` — request validation (like struct tags + validator in Go)

**Exercise:** Trace one request mentally: `POST /api/v1/chat` → `main.chat` → `orchestrator.chat` → `llm.complete`.

**You know it works when:** You can explain each file’s job without opening the code.

---

## 2.2 — Tool registry + `calculator` (first real tool)

**Goal:** One tool that runs in Python with **no LLM** — you call it directly in tests.

**Build:**

- `Tool` dataclass or class: `name`, `description`, `tier`, `execute(args) -> str`
- `ToolRegistry`: `register(tool)`, `get(name)`, `list_tools()`, `run(name, args)`
- `calculator` tool: safe math (`2 + 2`, `15 * 0.2`) — use `ast` or a safe math lib, **never** `eval()` on raw strings

**Files to create/edit:**

```
jarvis_ai/tools/
  base.py          # Tool interface
  calculator.py    # calculator implementation
  registry.py      # fill in the stub
```

**Python concepts:**

- `@dataclass`, type hints (`def run(self, args: dict) -> str`)
- `dict` for tool arguments (like `map[string]interface{}` in Go)
- unit tests in `tests/unit/test_calculator.py`

**You know it works when:**

```bash
pytest tests/unit/test_calculator.py -v
# registry.run("calculator", {"expression": "2+2"}) == "4"
```

**No API keys needed.**

---

## 2.3 — Agent loop (hardcoded tool choice)

**Goal:** Orchestrator decides to call a tool **without** the LLM yet — learn the loop shape.

**Build:**

- `Orchestrator.run_agent(message)`:
  1. If message contains `"calculate"` or looks like math → run `calculator`
  2. Else → normal `llm.complete(message)`

**Python concepts:**

- `if` / string checks (temporary — replaced in 2.4)
- returning structured results: `{"type": "tool_result", ...}` vs `{"type": "message", ...}`

**You know it works when:** Test sends `"calculate 3*4"` and gets `"12"` without calling OpenAI.

---

## 2.4 — LLM tool calling (real agent brain)

**Goal:** LLM chooses which tool to call using OpenAI/Anthropic **function/tool** APIs.

**Build:**

- Add `complete_with_tools(message, tools)` to `LLMProvider` (or a mixin)
- Pass tool JSON schemas from registry to the LLM
- Loop: LLM response → if `tool_calls` → run tool → send result back → LLM final answer
- Max iterations (e.g. 5) to avoid infinite loops

**Python concepts:**

- lists of dicts for API payloads
- `async for` in streaming (you already have this in orchestrator)
- reading vendor SDK docs (OpenAI `tools=`, Anthropic `tools=`)

**You know it works when:** With a real key, `"what is 99 * 101?"` triggers `calculator` and returns correct answer. With stub, mock the LLM returning a fake tool_call in tests.

---

## 2.5 — Policy tiers

**Goal:** Before running a tool, check `Tier` — safe runs immediately; confirm-required blocks.

**Build:**

- `policy/engine.py`: `check(tool_name, tier) -> ALLOW | NEEDS_CONFIRM | DENY`
- Register each tool with a tier in registry
- `calculator` → `SAFE`
- (prepare) `save_note` → `CONFIRM_REQUIRED`

**Python concepts:**

- `Enum` (already in `policy/policy.py`)
- match/case or if/elif chains

**You know it works when:** Unit test: confirm-required tool returns `NEEDS_CONFIRM` without executing.

---

## 2.6 — Notes tools + Postgres

**Goal:** `save_note` and `get_note` persist data.

**Build:**

- Migration: `notes` table (`id`, `user_id`, `content`, `created_at`)
- `save_note` / `get_note` tools
- Use `asyncpg` or SQLAlchemy (pick one, stick with it)
- Pass `user_id` from gateway header `X-User-ID` into orchestrator context

**Python concepts:**

- SQL parameters (`$1`, `$2`) — never string-concat SQL
- connection pools
- optional: `pytest` with test DB or SQLite for tests

**You know it works when:** Save a note, restart container, `get_note` still finds it.

---

## 2.7 — Confirm-required flow

**Goal:** When policy says confirm, pause and wait for user approval.

**Build:**

- `pending_actions` table or Redis key: `action_id`, `tool`, `args`, `user_id`, `status`
- API: `POST /api/v1/actions/{id}/approve` and `/reject`
- Orchestrator returns SSE event: `{"type": "confirm_required", "action_id": "..."}`
- After approve → run tool → continue agent loop

**Python concepts:**

- state machines (`pending` → `approved` → `executed`)
- FastAPI path params: `{id}`

**Optional Go work:** None required if Python owns policy. Later you can call Go `POLICY_SERVICE_URL`.

**You know it works when:** `save_note` waits until you hit approve endpoint, then saves.

---

## 2.8 — Reminders

**Goal:** `set_reminder` stores a reminder; `list_reminders` reads them.

**Build:**

- `reminders` table with `due_at`, `message`, `user_id`, `done`
- `set_reminder` → confirm-required
- Simple checker: cron job, or “on next message, surface due reminders” (MVP)

**You know it works when:** Set reminder for 1 min from now, ask later, JARVIS mentions it.

---

## 2.9 — Memory layer (Graphiti + Neo4j)

**Goal:** Long-term memory beyond notes table — “what did I tell you last week?”

**Build:**

- Add Neo4j + Graphiti to `docker-compose.yml`
- Implement `MemoryStore` in `jarvis_ai/memory/store.py`
- After chat turns, extract facts → write to memory
- Before answering, search memory → inject into LLM context

**This is the heaviest sub-phase.** Do not start until 2.2–2.8 feel comfortable.

**You know it works when:** Cold question across days returns correct fact without that fact in current chat history.

---

## Suggested weekly pace (slow)

| Week | Sub-phases | Focus |
|------|------------|--------|
| 1 | 2.1 + 2.2 | Read code + calculator + tests |
| 2 | 2.3 + 2.4 | Agent loop + LLM tools (stub tests first) |
| 3 | 2.5 + 2.6 | Policy + Postgres notes |
| 4 | 2.7 | Confirm flow |
| 5 | 2.8 | Reminders |
| 6+ | 2.9 | Graphiti memory |

Adjust pace — **understanding beats speed**.

---

## Python cheat sheet (for this project)

| You see | Meaning |
|---------|---------|
| `async def foo()` | Async function — call with `await foo()` |
| `await` | Wait for async work without blocking the server |
| `yield` | Produce one item in a generator/stream |
| `BaseModel` | Validated data class from JSON |
| `Settings()` | Loads `.env` into a typed object |
| `pytest` | Test runner (`go test` equivalent) |
| `from X import Y` | Import symbol Y from package X |

---

## What to do right now

**Start with 2.1 only** — read the seven files listed above.  
When ready, say: *“Let’s do sub-phase 2.2 — calculator and tool registry”* and we’ll implement it together with explanations line by line.

No API keys required until you want to test real LLM tool calling in 2.4.
