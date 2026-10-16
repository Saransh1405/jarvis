"""Durable job worker. Run as `python -m jarvis_ai.jobs`."""

import asyncio
import logging
from datetime import datetime, timezone

from jarvis_ai.actions.repository import PendingActionsRepository
from jarvis_ai.config.settings import Settings
from jarvis_ai.db import create_pool, run_migrations
from jarvis_ai.delivery import build_delivery_stack
from jarvis_ai.jobs.reminder_fire import ReminderFireHandler
from jarvis_ai.jobs.worker import ping_handler, run_once
from jarvis_ai.reminders.repository import RemindersRepository
from jarvis_ai.user_settings.repository import UserSettingsRepository

logger = logging.getLogger(__name__)


async def _loop() -> None:
    settings = Settings()
    if not settings.database_url:
        logger.error("DATABASE_URL is required for the job worker; waiting")
        while True:
            await asyncio.sleep(60)

    pool = await create_pool(settings.database_url)
    await run_migrations(pool)
    reminders = RemindersRepository(pool)
    user_settings = UserSettingsRepository(pool)
    pending = PendingActionsRepository(pool)
    stack = build_delivery_stack(pool, settings, user_settings, reminders, pending)
    handlers = {
        "ping": ping_handler,
        "reminder_fire": ReminderFireHandler(reminders, stack.notifier, stack.jobs),
        "daily_brief": stack.briefs.handle,
    }
    logger.info(
        "job worker started poll=%ss batch=%s",
        settings.worker_poll_interval_seconds,
        settings.worker_batch_size,
    )
    try:
        while True:
            try:
                await stack.jobs.heartbeat()
                await stack.briefs.ensure_scheduled(datetime.now(timezone.utc))
                claimed = await run_once(
                    stack.jobs,
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
        if stack.telegram_client is not None:
            await stack.telegram_client.aclose()
        await pool.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
