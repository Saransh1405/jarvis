# Phase 2 complete (Roadmap v2)

Phase 2 ships **multi-user persistence**: real auth, per-user chat history, tools with policy tiers, audit logs, and Postgres-backed long-term memory. Graphiti/Neo4j is **deferred** until Phase 5 (“what I know about you” UI); the `MemoryStore` interface stays swappable.

## v2 exit checklist

| Criterion | Status |
|-----------|--------|
| Two accounts, separate conversations and memory | Auth + conversations + isolation tests |
| Chat and memory survive restart | Postgres migrations + conversation/memory stores |
| Tool calls logged per `user_id` | `tool_call_logs` + Step 3 tests |
| “What did I tell you last week?” (private) | `remember_fact`, chat extraction, `search_memory`, prompt injection |

## What shipped (Steps 1–4)

1. **Auth** — Gateway signup/login, JWT → `X-User-ID`
2. **Conversations** — `conversations` / `messages`, history in agent loop
3. **Tools & policy** — Tier table, confirm via API, isolation + audit tests
4. **Memory** — `memory_facts`, `remember_fact`, rule-based chat extraction, deduped writes

## Memory (Postgres, not Graphiti)

- **Write:** `remember_fact` tool (Safe), chat extraction after each turn, `save_note` → memory index
- **Read:** System prompt injection + `search_memory` tool
- **Upgrade path:** Replace `PostgresMemoryStore` with Graphiti behind the same protocol in Phase 5+

## Confirm flow (until Phase 4 UI)

ConfirmRequired tools return `pending_action`. Approve with `POST /api/v1/actions/{id}/approve`. Phase 4 adds calendar/email OAuth and a plain **Yes/No** prompt in the Reach channel.

## Demo script

1. Sign up users A and B; chat as each with distinct JWTs.
2. User A: “My plumber is Raj, number 555-0100” (or `remember_fact`).
3. Restart stack; User A new conversation: “What did I tell you about the plumber?” → Raj/number in context or tool result.
4. User B asks the same → no leak.
5. Optional: `SELECT * FROM tool_call_logs WHERE user_id = ...`

## Next: Phase 3 Reach

See [`docs/Phase3_Getting_Started.md`](Phase3_Getting_Started.md) and [`docs/JARVIS_Roadmap_v2.md`](JARVIS_Roadmap_v2.md).

Tool audit notes: [`docs/Step3_tool_audit_verification.md`](Step3_tool_audit_verification.md).
