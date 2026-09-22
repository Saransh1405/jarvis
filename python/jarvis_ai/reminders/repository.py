from datetime import datetime, timezone

import asyncpg

from jarvis_ai.reminders.models import Reminder


class RemindersRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, user_id: str, message: str, due_at: datetime) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO reminders (user_id, message, due_at)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            user_id,
            message,
            due_at,
        )
        assert row is not None
        return str(row["id"])

    async def list_for_user(self, user_id: str, include_done: bool = False) -> list[Reminder]:
        if include_done:
            rows = await self._pool.fetch(
                """
                SELECT id::text, user_id, message, due_at, done
                FROM reminders
                WHERE user_id = $1
                ORDER BY due_at ASC
                """,
                user_id,
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id::text, user_id, message, due_at, done
                FROM reminders
                WHERE user_id = $1 AND done = FALSE
                ORDER BY due_at ASC
                """,
                user_id,
            )
        return [_row_to_reminder(row) for row in rows]

    async def list_due(self, user_id: str, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now(timezone.utc)
        rows = await self._pool.fetch(
            """
            SELECT id::text, user_id, message, due_at, done
            FROM reminders
            WHERE user_id = $1 AND done = FALSE AND due_at <= $2
            ORDER BY due_at ASC
            """,
            user_id,
            now,
        )
        return [_row_to_reminder(row) for row in rows]

    async def mark_done(self, user_id: str, reminder_id: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE reminders SET done = TRUE
            WHERE id = $1::uuid AND user_id = $2
            """,
            reminder_id,
            user_id,
        )
        return result.endswith("1")


def _row_to_reminder(row: asyncpg.Record) -> Reminder:
    due_at = row["due_at"]
    if not isinstance(due_at, datetime):
        due_at = datetime.fromisoformat(str(due_at))
    return Reminder(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        message=str(row["message"]),
        due_at=due_at,
        done=bool(row["done"]),
    )
