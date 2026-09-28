# Phase 2 — progress (Roadmap v2)

Phase 2 is delivered in steps: auth (Step 1), chat persistence (Step 2), tools/policy/audit (Step 3), memory polish (Step 4).

## Delivered

| Area | Feature |
|------|---------|
| Tools + agent loop | LLM tool calling, starter tools |
| Policy | `safe`, `confirm_required`; confirm requires `user_id` |
| Notes / reminders / memory | Postgres-backed, per-user |
| Pending actions | Approve/reject API + agent resume |
| Audit | `tool_call_logs` with `user_id` on executed tools |
| Conversations | Per-user threads in Postgres (Step 2) |

## Confirm flow (API only until Phase 4)

ConfirmRequired tools stop the agent and return `pending_action`. The user approves via:

- `POST /api/v1/actions/{action_id}/approve`
- `POST /api/v1/actions/{action_id}/reject`

Phase 4 (calendar/email) adds OAuth integrations and a **plain Yes/No** prompt in the Reach channel UI — not a separate generic confirm endpoint.

## Memory note

Postgres-backed memory (not Graphiti/Neo4j yet). Graphiti remains optional for Phase 5 “what I know about you” UI.

## Tool audit verification

See [`docs/Step3_tool_audit_verification.md`](Step3_tool_audit_verification.md).
