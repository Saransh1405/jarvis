"""Postgres job queue. Claim uses FOR UPDATE SKIP LOCKED."""

import json
from datetime import datetime, timedelta, timezone

import asyncpg

from jarvis_ai.jobs.models import ScheduledJob, backoff_seconds

_CLAIM_SQL = """
UPDATE scheduled_jobs
SET status = 'running',
    attempts = attempts + 1,
    locked_until = NOW() + make_interval(secs => $2::int),
    updated_at = NOW()
WHERE id IN (
    SELECT id FROM scheduled_jobs
    WHERE (status = 'scheduled' AND run_at <= NOW())
       OR (status = 'running' AND locked_until < NOW())
    ORDER BY run_at
    LIMIT $1
    FOR UPDATE SKIP LOCKED
)
RETURNING id, kind, user_id, run_at, payload, status, attempts, max_attempts,
          locked_until, last_error, dedupe_key
"""


def _row_to_job(row: asyncpg.Record) -> ScheduledJob:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return ScheduledJob(
        id=str(row["id"]),
        kind=str(row["kind"]),
        user_id=str(row["user_id"]),
        run_at=row["run_at"],
        payload=dict(payload or {}),
        status=str(row["status"]),
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        locked_until=row["locked_until"],
        last_error=row["last_error"],
        dedupe_key=row["dedupe_key"],
    )


class JobsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def enqueue(
        self,
        *,
        kind: str,
        user_id: str,
        run_at: datetime,
        payload: dict | None = None,
        dedupe_key: str | None = None,
        max_attempts: int = 5,
    ) -> ScheduledJob:
        row = await self._pool.fetchrow(
            """
            INSERT INTO scheduled_jobs (kind, user_id, run_at, payload, dedupe_key, max_attempts)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6)
            ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
            RETURNING id, kind, user_id, run_at, payload, status, attempts, max_attempts,
                      locked_until, last_error, dedupe_key
            """,
            kind,
            user_id,
            run_at,
            json.dumps(payload or {}),
            dedupe_key,
            max_attempts,
        )
        if row is None and dedupe_key:
            existing = await self._pool.fetchrow(
                """
                SELECT id, kind, user_id, run_at, payload, status, attempts, max_attempts,
                       locked_until, last_error, dedupe_key
                FROM scheduled_jobs
                WHERE dedupe_key = $1
                """,
                dedupe_key,
            )
            assert existing is not None
            if str(existing["status"]) == "cancelled":
                revived = await self._pool.fetchrow(
                    """
                    UPDATE scheduled_jobs
                    SET status = 'scheduled',
                        run_at = $2,
                        payload = $3::jsonb,
                        attempts = 0,
                        locked_until = NULL,
                        last_error = NULL,
                        updated_at = NOW()
                    WHERE id = $1::uuid
                    RETURNING id, kind, user_id, run_at, payload, status, attempts, max_attempts,
                              locked_until, last_error, dedupe_key
                    """,
                    str(existing["id"]),
                    run_at,
                    json.dumps(payload or {}),
                )
                assert revived is not None
                return _row_to_job(revived)
            return _row_to_job(existing)
        assert row is not None
        return _row_to_job(row)

    async def claim(self, now: datetime, lease_seconds: int, batch_size: int) -> list[ScheduledJob]:
        del now  # the SQL clock is the database clock
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(_CLAIM_SQL, batch_size, lease_seconds)
        return [_row_to_job(row) for row in rows]

    async def complete(self, job_id: str) -> None:
        await self._pool.execute(
            """
            UPDATE scheduled_jobs
            SET status = 'done', locked_until = NULL, updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
        )

    async def fail(self, job: ScheduledJob, error: str, now: datetime) -> None:
        if job.attempts >= job.max_attempts:
            await self._pool.execute(
                """
                UPDATE scheduled_jobs
                SET status = 'failed', locked_until = NULL, last_error = $2, updated_at = NOW()
                WHERE id = $1::uuid
                """,
                job.id,
                error[:500],
            )
            return
        run_at = now.astimezone(timezone.utc) + timedelta(seconds=backoff_seconds(job.attempts))
        await self._pool.execute(
            """
            UPDATE scheduled_jobs
            SET status = 'scheduled',
                run_at = $2,
                locked_until = NULL,
                last_error = $3,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job.id,
            run_at,
            error[:500],
        )

    async def cancel_by_dedupe(self, dedupe_key: str) -> None:
        await self._pool.execute(
            """
            UPDATE scheduled_jobs
            SET status = 'cancelled', locked_until = NULL, updated_at = NOW()
            WHERE dedupe_key = $1 AND status IN ('scheduled', 'running')
            """,
            dedupe_key,
        )

    async def has_pending(self, *, kind: str, user_id: str) -> bool:
        found = await self._pool.fetchval(
            """
            SELECT 1 FROM scheduled_jobs
            WHERE kind = $1 AND user_id = $2 AND status IN ('scheduled', 'running')
            LIMIT 1
            """,
            kind,
            user_id,
        )
        return found is not None

    async def heartbeat(self, worker_id: str = "default") -> None:
        await self._pool.execute(
            """
            INSERT INTO worker_heartbeats (id, beat_at)
            VALUES ($1, NOW())
            ON CONFLICT (id) DO UPDATE SET beat_at = NOW()
            """,
            worker_id,
        )
