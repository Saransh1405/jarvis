from datetime import datetime, timezone

import asyncpg

from jarvis_ai.reminders.models import Reminder

_COLUMNS = """
    id::text, user_id, message, due_at, done, timezone, status,
    last_fired_at, rrule, lead_minutes, source
"""

_TERMINAL = ("done", "cancelled")


class RemindersRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        user_id: str,
        message: str,
        due_at: datetime,
        *,
        timezone: str = "UTC",
        rrule: str | None = None,
        source: str = "chat",
        lead_minutes: int | None = None,
        status: str = "scheduled",
    ) -> str:
        done = status in _TERMINAL
        row = await self._pool.fetchrow(
            """
            INSERT INTO reminders (
                user_id, message, due_at, done, timezone, status, rrule, lead_minutes, source
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id::text
            """,
            user_id,
            message,
            due_at,
            done,
            timezone,
            status,
            rrule,
            lead_minutes,
            source,
        )
        assert row is not None
        return str(row["id"])

    async def get(self, reminder_id: str) -> Reminder | None:
        row = await self._fetch_one(
            f"SELECT {_COLUMNS} FROM reminders WHERE id = $1::uuid",
            reminder_id,
        )
        if row is None:
            return None
        return _row_to_reminder(row)

    async def get_for_user(self, user_id: str, reminder_id: str) -> Reminder | None:
        row = await self._fetch_one(
            f"SELECT {_COLUMNS} FROM reminders WHERE id = $1::uuid AND user_id = $2",
            reminder_id,
            user_id,
        )
        if row is None:
            return None
        return _row_to_reminder(row)

    async def list_for_user(self, user_id: str, include_done: bool = False) -> list[Reminder]:
        if include_done:
            rows = await self._pool.fetch(
                f"""
                SELECT {_COLUMNS}
                FROM reminders
                WHERE user_id = $1
                ORDER BY due_at ASC
                """,
                user_id,
            )
        else:
            rows = await self._pool.fetch(
                f"""
                SELECT {_COLUMNS}
                FROM reminders
                WHERE user_id = $1 AND done = FALSE
                ORDER BY due_at ASC
                """,
                user_id,
            )
        return [_row_to_reminder(row) for row in rows]

    async def list_due(self, user_id: str, now: datetime | None = None) -> list[Reminder]:
        moment = now or datetime.now(timezone.utc)
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS}
            FROM reminders
            WHERE user_id = $1 AND done = FALSE AND due_at <= $2
            ORDER BY due_at ASC
            """,
            user_id,
            moment,
        )
        return [_row_to_reminder(row) for row in rows]

    async def list_between(
        self,
        user_id: str,
        start: datetime,
        end: datetime,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Reminder]:
        if statuses:
            rows = await self._pool.fetch(
                f"""
                SELECT {_COLUMNS}
                FROM reminders
                WHERE user_id = $1 AND due_at >= $2 AND due_at < $3 AND status = ANY($4::text[])
                ORDER BY due_at ASC
                """,
                user_id,
                start,
                end,
                list(statuses),
            )
        else:
            rows = await self._pool.fetch(
                f"""
                SELECT {_COLUMNS}
                FROM reminders
                WHERE user_id = $1 AND due_at >= $2 AND due_at < $3
                  AND status <> ALL($4::text[])
                ORDER BY due_at ASC
                """,
                user_id,
                start,
                end,
                list(_TERMINAL),
            )
        return [_row_to_reminder(row) for row in rows]

    async def apply_delivery(
        self,
        reminder_id: str,
        *,
        status: str,
        due_at: datetime | None = None,
        last_fired_at: datetime | None = None,
        done: bool | None = None,
    ) -> bool:
        done_flag = status in _TERMINAL if done is None else done
        result = await self._pool.execute(
            """
            UPDATE reminders
            SET status = $2,
                done = $3,
                due_at = COALESCE($4, due_at),
                last_fired_at = COALESCE($5, last_fired_at)
            WHERE id = $1::uuid
            """,
            reminder_id,
            status,
            done_flag,
            due_at,
            last_fired_at,
        )
        return result.endswith("1")

    async def mark_done(self, user_id: str, reminder_id: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE reminders SET done = TRUE, status = 'done'
            WHERE id = $1::uuid AND user_id = $2
            """,
            reminder_id,
            user_id,
        )
        return result.endswith("1")

    async def _fetch_one(self, sql: str, *args: object) -> asyncpg.Record | None:
        try:
            return await self._pool.fetchrow(sql, *args)
        except asyncpg.DataError:
            return None


def _row_to_reminder(row: asyncpg.Record) -> Reminder:
    return Reminder(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        message=str(row["message"]),
        due_at=_as_datetime(row["due_at"]),
        done=bool(row["done"]),
        timezone=str(row["timezone"] or "UTC"),
        status=str(row["status"] or "scheduled"),
        last_fired_at=_as_datetime(row["last_fired_at"]) if row["last_fired_at"] else None,
        rrule=row["rrule"],
        lead_minutes=row["lead_minutes"],
        source=str(row["source"] or "chat"),
    )


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
