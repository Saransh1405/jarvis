# Step 3 — tool audit verification

Confirms executed tools are logged per user. Unit tests cover this in CI (`test_tool_call_audit.py`, `test_user_isolation.py`).

## Automated (CI)

```bash
cd python && pytest tests/unit/test_tool_call_audit.py tests/unit/test_user_isolation.py -v
```

## Manual (full stack + gateway)

1. Sign up two users via gateway; save tokens and `user_id` from each response.
2. Run calculator chat as user A and user B (stub or real LLM):

```bash
curl -s -X POST http://localhost:8080/api/v1/chat \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"message":"what is 12*12?"}'
```

3. Query audit rows:

```sql
SELECT user_id, tool_name, created_at
FROM tool_call_logs
ORDER BY created_at DESC
LIMIT 10;
```

Expect distinct `user_id` values for A and B when each ran `calculator`.

4. Approve flow: trigger `save_note`, approve with same user JWT, confirm a `save_note` row for that `user_id` only.
