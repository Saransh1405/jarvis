"""Postgres-backed notes storage."""

from datetime import datetime

import asyncpg

from jarvis_ai.notes.models import Note


class NotesRepository:
    """Persist notes per user."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, user_id: str, content: str) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO notes (user_id, content)
            VALUES ($1, $2)
            RETURNING id::text
            """,
            user_id,
            content,
        )
        assert row is not None
        return str(row["id"])

    async def get_for_user(self, user_id: str, note_id: str) -> Note | None:
        row = await self._pool.fetchrow(
            """
            SELECT id::text, user_id, content, created_at
            FROM notes
            WHERE user_id = $1 AND id = $2::uuid
            """,
            user_id,
            note_id,
        )
        if row is None:
            return None
        return _row_to_note(row)

    async def list_recent(self, user_id: str, limit: int = 10) -> list[Note]:
        rows = await self._pool.fetch(
            """
            SELECT id::text, user_id, content, created_at
            FROM notes
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_row_to_note(row) for row in rows]


def _row_to_note(row: asyncpg.Record) -> Note:
    created_at = row["created_at"]
    if not isinstance(created_at, datetime):
        created_at = datetime.fromisoformat(str(created_at))
    return Note(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        content=str(row["content"]),
        created_at=created_at,
    )
