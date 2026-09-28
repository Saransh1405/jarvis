"""Postgres-backed conversations storage."""

import json
from datetime import datetime
from typing import Any

import asyncpg

from jarvis_ai.conversations.models import Conversation, Message


def _row_to_conversation(row: asyncpg.Record) -> Conversation:
    return Conversation(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_message(row: asyncpg.Record) -> Message:
    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return Message(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        user_id=str(row["user_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        metadata=dict(meta or {}),
        created_at=row["created_at"],
    )


class ConversationsRepository:
    """Persist chat threads per user."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_conversation(self, user_id: str) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO conversations (user_id)
            VALUES ($1)
            RETURNING id::text
            """,
            user_id,
        )
        assert row is not None
        return str(row["id"])

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM conversations
            WHERE user_id = $1 AND id = $2::uuid
            """,
            user_id,
            conversation_id,
        )
        if row is None:
            return None
        return _row_to_conversation(row)

    async def touch_conversation(self, conversation_id: str) -> None:
        await self._pool.execute(
            """
            UPDATE conversations SET updated_at = NOW()
            WHERE id = $1::uuid
            """,
            conversation_id,
        )

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO messages (conversation_id, user_id, role, content, metadata)
            VALUES ($1::uuid, $2, $3, $4, $5::jsonb)
            """,
            conversation_id,
            user_id,
            role,
            content,
            json.dumps(metadata or {}),
        )
        await self.touch_conversation(conversation_id)

    async def list_messages(
        self, user_id: str, conversation_id: str, limit: int = 100
    ) -> list[Message]:
        rows = await self._pool.fetch(
            """
            SELECT id, conversation_id, user_id, role, content, metadata, created_at
            FROM (
                SELECT m.id, m.conversation_id, m.user_id, m.role, m.content, m.metadata, m.created_at
                FROM messages m
                INNER JOIN conversations c ON c.id = m.conversation_id
                WHERE c.user_id = $1 AND m.conversation_id = $2::uuid
                ORDER BY m.created_at DESC
                LIMIT $3
            ) recent
            ORDER BY created_at ASC
            """,
            user_id,
            conversation_id,
            limit,
        )
        return [_row_to_message(row) for row in rows]

    async def list_conversations(self, user_id: str, limit: int = 20) -> list[Conversation]:
        rows = await self._pool.fetch(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM conversations
            WHERE user_id = $1
            ORDER BY updated_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_row_to_conversation(row) for row in rows]
