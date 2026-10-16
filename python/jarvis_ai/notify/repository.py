import asyncpg


class NotificationsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        *,
        user_id: str,
        kind: str,
        channel: str,
        status: str,
        dedupe_key: str | None = None,
        ref_id: str | None = None,
        error: str | None = None,
        body: str | None = None,
    ) -> str | None:
        row = await self._pool.fetchrow(
            """
            INSERT INTO notifications (user_id, kind, channel, status, dedupe_key, ref_id, error, body, sent_at)
            VALUES ($1, $2, $3, $4, $5, $6::uuid, $7, $8, CASE WHEN $4 = 'sent' THEN NOW() ELSE NULL END)
            ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'sent')
            DO NOTHING
            RETURNING id::text
            """,
            user_id,
            kind,
            channel,
            status,
            dedupe_key,
            ref_id,
            error,
            body,
        )
        if row is None:
            return None
        return str(row["id"])

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[dict]:
        rows = await self._pool.fetch(
            """
            SELECT id::text, kind, channel, status, ref_id::text AS ref_id, error, body,
                   created_at, sent_at
            FROM notifications
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_notification_row(row) for row in rows]

    async def mark(self, notification_id: str, status: str, error: str | None = None) -> None:
        await self._pool.execute(
            """
            UPDATE notifications
            SET status = $2,
                error = $3,
                sent_at = CASE WHEN $2 = 'sent' THEN NOW() ELSE sent_at END
            WHERE id = $1::uuid
            """,
            notification_id,
            status,
            error,
        )


def _notification_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "kind": str(row["kind"]),
        "channel": str(row["channel"]),
        "status": str(row["status"]),
        "ref_id": row["ref_id"],
        "error": row["error"],
        "body": row["body"],
        "created_at": row["created_at"],
        "sent_at": row["sent_at"],
    }
