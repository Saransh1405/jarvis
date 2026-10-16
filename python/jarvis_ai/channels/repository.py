"""Postgres channel links, one-time tokens, and webhook dedupe."""

from datetime import datetime, timezone
from uuid import uuid4

import asyncpg

from jarvis_ai.channels.base import UserChannel
from jarvis_ai.channels.linking import apply_link


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _row_to_channel(row: asyncpg.Record) -> UserChannel:
    return UserChannel(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        channel=str(row["channel"]),
        external_id=str(row["external_id"]),
        external_username=row["external_username"],
        status=str(row["status"]),
        linked_at=row["linked_at"],
    )


class ChannelsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_link_token(
        self, user_id: str, channel: str, token_hash: bytes, expires_at: datetime
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO channel_link_tokens (token_hash, user_id, channel, expires_at)
            VALUES ($1, $2, $3, $4)
            """,
            token_hash,
            user_id,
            channel,
            expires_at,
        )

    async def consume_link_token(self, token_hash: bytes, channel: str, now: datetime) -> str | None:
        row = await self._pool.fetchrow(
            """
            UPDATE channel_link_tokens
            SET used_at = $3
            WHERE token_hash = $1
              AND channel = $2
              AND used_at IS NULL
              AND expires_at > $3
            RETURNING user_id
            """,
            token_hash,
            channel,
            now,
        )
        if row is None:
            return None
        return str(row["user_id"])

    async def get_by_external(self, channel: str, external_id: str) -> UserChannel | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, user_id, channel, external_id, external_username, status, linked_at
            FROM user_channels
            WHERE channel = $1 AND external_id = $2
            """,
            channel,
            external_id,
        )
        if row is None:
            return None
        return _row_to_channel(row)

    async def get_for_user(self, user_id: str, channel: str) -> UserChannel | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, user_id, channel, external_id, external_username, status, linked_at
            FROM user_channels
            WHERE user_id = $1 AND channel = $2
            """,
            user_id,
            channel,
        )
        if row is None:
            return None
        return _row_to_channel(row)

    async def link(
        self,
        user_id: str,
        channel: str,
        external_id: str,
        username: str | None,
        now: datetime | None = None,
    ) -> str:
        moment = _aware(now or datetime.now(timezone.utc))
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, channel, external_id, external_username, status, linked_at
                    FROM user_channels
                    WHERE (channel = $1 AND external_id = $2)
                       OR (user_id = $3 AND channel = $1)
                    FOR UPDATE
                    """,
                    channel,
                    external_id,
                    user_id,
                )
                current = [_row_to_channel(row) for row in rows]
                updated, code = apply_link(
                    current,
                    user_id=user_id,
                    channel=channel,
                    external_id=external_id,
                    username=username,
                    now=moment,
                    new_id=str(uuid4()),
                )
                if code != "ok":
                    return code
                ids = [row["id"] for row in rows]
                if ids:
                    await conn.execute(
                        "DELETE FROM user_channels WHERE id = ANY($1::uuid[])",
                        ids,
                    )
                for row in updated:
                    await conn.execute(
                        """
                        INSERT INTO user_channels (
                            id, user_id, channel, external_id, external_username, status, linked_at
                        )
                        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
                        """,
                        row.id,
                        row.user_id,
                        row.channel,
                        row.external_id,
                        row.external_username,
                        row.status,
                        row.linked_at or moment,
                    )
                return "ok"

    async def set_status(self, user_id: str, channel: str, status: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE user_channels
            SET status = $3
            WHERE user_id = $1 AND channel = $2
            """,
            user_id,
            channel,
            status,
        )
        return result.endswith("1")

    async def touch_inbound(self, channel: str, external_id: str) -> None:
        await self._pool.execute(
            """
            UPDATE user_channels
            SET last_inbound_at = NOW()
            WHERE channel = $1 AND external_id = $2
            """,
            channel,
            external_id,
        )

    async def mark_update_seen(self, channel: str, update_id: int) -> bool:
        row = await self._pool.fetchrow(
            """
            INSERT INTO channel_updates_seen (channel, update_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING update_id
            """,
            channel,
            update_id,
        )
        return row is not None

    async def purge_old_updates(self, older_than: datetime) -> None:
        await self._pool.execute(
            "DELETE FROM channel_updates_seen WHERE received_at < $1",
            older_than,
        )

    async def user_label(self, user_id: str) -> str:
        try:
            row = await self._pool.fetchrow(
                "SELECT email FROM users WHERE id = $1::uuid",
                user_id,
            )
        except Exception:
            return "your account"
        if row is None or not row["email"]:
            return "your account"
        email = str(row["email"])
        local = email.split("@", 1)[0].strip()
        return local or "your account"
