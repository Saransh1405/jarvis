# Phase 2 — Complete

All Phase 2 sub-phases (2.1–2.9) are implemented in this repository.

## Delivered

| Sub-phase | Feature |
|-----------|---------|
| 2.2–2.4 | Tools + agent loop + LLM tool calling |
| 2.5 | Policy engine (`safe`, `confirm_required`, `deny`) |
| 2.6 | Notes in Postgres (`save_note`, `get_note`) |
| 2.7 | Pending actions + approve/reject API + agent resume |
| 2.8 | Reminders (`set_reminder`, `list_reminders`, due surfacing) |
| 2.9 | Long-term memory (Postgres `memory_facts`, `search_memory` tool) |

Also: `tool_call_logs` audit table, gateway proxies for action endpoints, GitHub Actions CI.

## Try confirm flow

```bash
# 1. Login via gateway, get token
# 2. Chat with save_note intent (use real LLM or scripted tests)
# 3. POST /api/v1/actions/{action_id}/approve with same user JWT
```

## Memory note

Phase 2.9 uses **Postgres-backed memory** (not Graphiti/Neo4j yet). That matches the roadmap demo (“what did I tell you last week?”) with less ops. Graphiti can replace `PostgresMemoryStore` in a later iteration.

## Next

See **`docs/Phase3_Getting_Started.md`**.
