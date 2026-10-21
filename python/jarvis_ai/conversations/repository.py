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

    async def create_conversation(
        self,
        user_id: str,
        *,
        channel: str = "web",
        channel_chat_id: str | None = None,
    ) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO conversations (user_id, channel, channel_chat_id)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            user_id,
            channel,
            channel_chat_id,
        )
        assert row is not None
        return str(row["id"])

    async def latest_channel_conversation(
        self, user_id: str, channel: str, channel_chat_id: str
    ) -> str | None:
        row = await self._pool.fetchrow(
            """
            SELECT id::text
            FROM conversations
            WHERE user_id = $1 AND channel = $2 AND channel_chat_id = $3
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            user_id,
            channel,
            channel_chat_id,
        )
        if row is None:
            return None
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

    async def get_summary(self, user_id: str, conversation_id: str) -> str | None:
        value = await self._pool.fetchval(
            """
            SELECT summary
            FROM conversations
            WHERE user_id = $1 AND id = $2::uuid
            """,
            user_id,
            conversation_id,
        )
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    async def set_summary(self, user_id: str, conversation_id: str, summary: str) -> None:
        await self._pool.execute(
            """
            UPDATE conversations
            SET summary = $3, updated_at = NOW()
            WHERE user_id = $1 AND id = $2::uuid
            """,
            user_id,
            conversation_id,
            summary,
        )

    async def count_user_messages(self, user_id: str, conversation_id: str) -> int:
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)
            FROM messages m
            INNER JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = $1 AND m.conversation_id = $2::uuid AND m.role = 'user'
            """,
            user_id,
            conversation_id,
        )
        return int(value or 0)

    async def latest_user_message_id(self, user_id: str, conversation_id: str) -> str | None:
        value = await self._pool.fetchval(
            """
            SELECT m.id::text
            FROM messages m
            INNER JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = $1 AND m.conversation_id = $2::uuid AND m.role = 'user'
            ORDER BY m.created_at DESC
            LIMIT 1
            """,
            user_id,
            conversation_id,
        )
        if value is None:
            return None
        return str(value)

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
