"""Persist agent actions awaiting user confirmation."""

import json
from datetime import datetime
from typing import Any

import asyncpg

from jarvis_ai.actions.models import PendingActionRecord


class PendingActionsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        user_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        messages: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO pending_actions (
                user_id, conversation_id, tool_call_id, tool_name, arguments, messages
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
            RETURNING id::text
            """,
            user_id,
            conversation_id,
            tool_call_id,
            tool_name,
            json.dumps(arguments),
            json.dumps(messages),
        )
        assert row is not None
        return str(row["id"])

    async def get_for_user(self, action_id: str, user_id: str) -> PendingActionRecord | None:
        row = await self._pool.fetchrow(
            """
            SELECT id::text, user_id, conversation_id, tool_call_id, tool_name,
                   arguments, messages, status, created_at
            FROM pending_actions
            WHERE id = $1::uuid AND user_id = $2
            """,
            action_id,
            user_id,
        )
        if row is None:
            return None
        return _row_to_record(row)

    async def set_status(self, action_id: str, user_id: str, status: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE pending_actions
            SET status = $3, updated_at = NOW()
            WHERE id = $1::uuid AND user_id = $2 AND status = 'pending'
            """,
            action_id,
            user_id,
            status,
        )
        return result.endswith("1")


def _row_to_record(row: asyncpg.Record) -> PendingActionRecord:
    args = row["arguments"]
    if isinstance(args, str):
        args = json.loads(args)
    messages = row["messages"]
    if isinstance(messages, str):
        messages = json.loads(messages)
    created_at = row["created_at"]
    if not isinstance(created_at, datetime):
        created_at = datetime.fromisoformat(str(created_at))
    return PendingActionRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        conversation_id=row["conversation_id"],
        tool_call_id=str(row["tool_call_id"]),
        tool_name=str(row["tool_name"]),
        arguments=dict(args),
        messages=list(messages),
        status=str(row["status"]),
        created_at=created_at,
    )
