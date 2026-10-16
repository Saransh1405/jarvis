"""Deliver one reminder occurrence, then schedule the next repeat."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from jarvis_ai.channels.base import Button, OutboundMessage
from jarvis_ai.jobs.models import ScheduledJob
from jarvis_ai.reminders.schedule import (
    _as_utc,
    is_late,
    next_occurrence,
    occurrence_token,
    parse_occurrence,
    reminder_dedupe_key,
)
from jarvis_ai.user_settings.formatting import format_datetime_local

logger = logging.getLogger(__name__)


class ReminderFireHandler:
    def __init__(self, reminders, notifier, jobs, clock: Callable[[], datetime] | None = None) -> None:
        self._reminders = reminders
        self._notifier = notifier
        self._jobs = jobs
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def __call__(self, job: ScheduledJob) -> None:
        await deliver_reminder(
            job,
            reminders=self._reminders,
            notifier=self._notifier,
            jobs=self._jobs,
            now=self._clock(),
        )


async def deliver_reminder(job: ScheduledJob, *, reminders, notifier, jobs, now: datetime) -> None:
    reminder_id = str(job.payload.get("reminder_id") or "")
    if not reminder_id:
        raise RuntimeError("reminder_fire missing reminder_id")
    reminder = await reminders.get(reminder_id)
    if reminder is None or reminder.user_id != job.user_id:
        logger.info("reminder_fire skipped missing reminder_id=%s", reminder_id)
        return
    if reminder.status in ("cancelled", "done"):
        logger.info("reminder_fire skipped status=%s reminder_id=%s", reminder.status, reminder.id)
        return

    occurrence = str(job.payload.get("occurrence_ts") or occurrence_token(job.run_at))
    original = parse_occurrence(occurrence) or job.run_at
    lag = int((_as_utc(now) - _as_utc(job.run_at)).total_seconds())
    logger.info(
        "reminder_delivery_lag_seconds=%s reminder_id=%s user_id=%s",
        lag,
        reminder.id,
        job.user_id,
    )

    text = reminder.message
    if is_late(job.run_at, now):
        local = format_datetime_local(original, reminder.timezone)
        text = f"Late reminder (originally {local}): {reminder.message}"

    dedupe_key = job.dedupe_key or reminder_dedupe_key(reminder.id, original)
    result = await notifier.notify(
        job.user_id,
        "reminder",
        OutboundMessage(text=text, format="plain", buttons=_buttons(reminder.id)),
        dedupe_key=dedupe_key,
        bypass_quiet_hours=True,
        ref_id=reminder.id,
    )
    if result.status not in ("sent", "deduped"):
        raise RuntimeError(result.error or f"reminder notify {result.status}")

    if occurrence_token(reminder.due_at) != occurrence:
        return

    if reminder.rrule:
        nxt = next_occurrence(reminder.rrule, reminder.due_at, reminder.timezone)
        if nxt is None:
            await reminders.apply_delivery(
                reminder.id, status="fired", last_fired_at=now, done=False
            )
            return
        await reminders.apply_delivery(
            reminder.id,
            status="scheduled",
            due_at=nxt,
            last_fired_at=now,
            done=False,
        )
        await jobs.enqueue(
            kind="reminder_fire",
            user_id=reminder.user_id,
            run_at=nxt,
            payload={"reminder_id": reminder.id, "occurrence_ts": occurrence_token(nxt)},
            dedupe_key=reminder_dedupe_key(reminder.id, nxt),
        )
        return

    await reminders.apply_delivery(reminder.id, status="fired", last_fired_at=now, done=False)


def _buttons(reminder_id: str) -> list[list[Button]]:
    return [[
        Button(text="Done", callback_data=f"d:{reminder_id}"),
        Button(text="10m", callback_data=f"s10:{reminder_id}"),
        Button(text="1h", callback_data=f"s60:{reminder_id}"),
        Button(text="Tomorrow", callback_data=f"st:{reminder_id}"),
    ]]
