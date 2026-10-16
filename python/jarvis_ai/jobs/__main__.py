"""Durable job worker. Run as `python -m jarvis_ai.jobs`."""

import asyncio
import logging

from jarvis_ai.config.settings import Settings
from jarvis_ai.db import create_pool, run_migrations
from jarvis_ai.jobs.repository import JobsRepository
from jarvis_ai.jobs.worker import ping_handler, run_once

logger = logging.getLogger(__name__)


async def _loop() -> None:
    settings = Settings()
    if not settings.database_url:
        logger.error("DATABASE_URL is required for the job worker; waiting")
        while True:
            await asyncio.sleep(60)

    pool = await create_pool(settings.database_url)
    await run_migrations(pool)
    queue = JobsRepository(pool)
    handlers = {"ping": ping_handler}
    logger.info(
        "job worker started poll=%ss batch=%s",
        settings.worker_poll_interval_seconds,
        settings.worker_batch_size,
    )
    try:
        while True:
            try:
                await queue.heartbeat()
                claimed = await run_once(
                    queue,
                    handlers,
                    lease_seconds=settings.job_lease_seconds,
                    batch_size=settings.worker_batch_size,
                )
                if claimed:
                    logger.info("claimed %s job(s)", claimed)
            except Exception:
                logger.exception("job worker iteration failed")
            await asyncio.sleep(settings.worker_poll_interval_seconds)
    finally:
        await pool.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
