"""In-memory job queue mirroring the Postgres claim rules."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jarvis_ai.jobs.models import ScheduledJob, backoff_seconds


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.jobs: dict[str, ScheduledJob] = {}

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
        if dedupe_key:
            for existing in self.jobs.values():
                if existing.dedupe_key == dedupe_key:
                    return existing
        job = ScheduledJob(
            id=str(uuid4()),
            kind=kind,
            user_id=user_id,
            run_at=_aware(run_at),
            payload=dict(payload or {}),
            dedupe_key=dedupe_key,
            max_attempts=max_attempts,
        )
        self.jobs[job.id] = job
        return job

    async def claim(self, now: datetime, lease_seconds: int, batch_size: int) -> list[ScheduledJob]:
        moment = _aware(now)
        due: list[ScheduledJob] = []
        for job in self.jobs.values():
            runnable = job.status == "scheduled" and _aware(job.run_at) <= moment
            reclaim = (
                job.status == "running"
                and job.locked_until is not None
                and _aware(job.locked_until) < moment
            )
            if runnable or reclaim:
                due.append(job)
        due.sort(key=lambda job: _aware(job.run_at))
        claimed: list[ScheduledJob] = []
        for job in due[:batch_size]:
            job.status = "running"
            job.attempts += 1
            job.locked_until = moment + timedelta(seconds=lease_seconds)
            claimed.append(job)
        return claimed

    async def complete(self, job_id: str) -> None:
        job = self.jobs[job_id]
        job.status = "done"
        job.locked_until = None

    async def fail(self, job: ScheduledJob, error: str, now: datetime) -> None:
        moment = _aware(now)
        current = self.jobs[job.id]
        current.last_error = error[:500]
        current.locked_until = None
        if current.attempts >= current.max_attempts:
            current.status = "failed"
            return
        current.status = "scheduled"
        current.run_at = moment + timedelta(seconds=backoff_seconds(current.attempts))

    async def cancel_by_dedupe(self, dedupe_key: str) -> None:
        for job in self.jobs.values():
            if job.dedupe_key == dedupe_key and job.status in ("scheduled", "running"):
                job.status = "cancelled"
                job.locked_until = None
