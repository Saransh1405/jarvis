"""Done, snooze, and cancel. Tools and Telegram buttons share this."""

from datetime import datetime

from jarvis_ai.reminders.models import Reminder
from jarvis_ai.reminders.schedule import reminder_dedupe_key, snooze_until
from jarvis_ai.user_settings.formatting import format_datetime_local


async def cancel_reminder(reminders, jobs, reminder: Reminder) -> str:
    if reminder.status in ("cancelled", "done"):
        return f"That reminder is already {reminder.status}."
    await reminders.apply_delivery(reminder.id, status="cancelled", done=True)
    if jobs is not None:
        await jobs.cancel_by_dedupe(reminder_dedupe_key(reminder.id, reminder.due_at))
    return f"Cancelled reminder {reminder.id}."


async def complete_reminder(reminders, jobs, reminder: Reminder) -> str:
    if reminder.status == "done":
        return "That reminder is already done."
    if reminder.status == "cancelled":
        return "That reminder is already cancelled."
    await reminders.apply_delivery(reminder.id, status="done", done=True)
    if jobs is not None:
        await jobs.cancel_by_dedupe(reminder_dedupe_key(reminder.id, reminder.due_at))
    return "Marked done."


async def snooze_reminder(
    reminders,
    jobs,
    reminder: Reminder,
    *,
    kind: str,
    now: datetime,
) -> str:
    if reminder.status in ("cancelled", "done"):
        return f"That reminder is already {reminder.status}."
    if jobs is None:
        return "Error: reminder scheduling is not configured."
    until = snooze_until(kind, now=now, due_at=reminder.due_at, tz_name=reminder.timezone)
    if until is None:
        return "Error: snooze must be 10 minutes, 1 hour, or tomorrow."
    await jobs.cancel_by_dedupe(reminder_dedupe_key(reminder.id, reminder.due_at))
    await reminders.apply_delivery(reminder.id, status="snoozed", due_at=until, done=False)
    await jobs.enqueue(
        kind="reminder_fire",
        user_id=reminder.user_id,
        run_at=until,
        payload={"reminder_id": reminder.id, "occurrence_ts": _token(until)},
        dedupe_key=reminder_dedupe_key(reminder.id, until),
    )
    label = format_datetime_local(until, reminder.timezone)
    return f"Snoozed until {label}."


def _token(due_at: datetime) -> str:
    from jarvis_ai.reminders.schedule import occurrence_token

    return occurrence_token(due_at)
