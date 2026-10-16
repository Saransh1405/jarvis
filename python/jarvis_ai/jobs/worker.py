"""One claim cycle. The process loop lives in jarvis_ai.jobs.__main__."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from jarvis_ai.jobs.models import ScheduledJob

logger = logging.getLogger(__name__)

JobHandler = Callable[[ScheduledJob], Awaitable[None]]


async def run_once(
    queue,
    handlers: dict[str, JobHandler],
    *,
    now: datetime | None = None,
    lease_seconds: int = 60,
    batch_size: int = 20,
) -> int:
    moment = now or datetime.now(timezone.utc)
    jobs = await queue.claim(moment, lease_seconds, batch_size)
    for job in jobs:
        handler = handlers.get(job.kind)
        try:
            if handler is None:
                raise RuntimeError(f"no handler for job kind {job.kind}")
            await handler(job)
            await queue.complete(job.id)
        except Exception as exc:
            logger.exception("job %s kind=%s failed", job.id, job.kind)
            await queue.fail(job, str(exc), moment)
    return len(jobs)


async def ping_handler(job: ScheduledJob) -> None:
    """Test and heartbeat-style job. Succeeds unless payload says otherwise."""
    if job.payload.get("fail"):
        raise RuntimeError(str(job.payload.get("error") or "ping failed"))
