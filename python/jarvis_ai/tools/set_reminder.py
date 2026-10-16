from datetime import datetime, timezone
from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.reminders.schedule import (
    ASK_RECURRENCE,
    first_future,
    occurrence_token,
    recurrence_to_rrule,
    reminder_dedupe_key,
)
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext
from jarvis_ai.user_settings.formatting import format_datetime_local
from jarvis_ai.user_settings.tz import resolve_zone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_due_at(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    due = datetime.fromisoformat(text)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return due


async def _run_set_reminder(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to set reminders."
    if ctx.reminders is None:
        return "Error: reminders storage is not configured."

    message = str(args.get("message", "")).strip()
    due_raw = args.get("due_at")
    if not message:
        return "Error: reminder message cannot be empty."
    if not isinstance(due_raw, str) or not due_raw.strip():
        return "Error: due_at must be an ISO-8601 timestamp."

    try:
        due_at = _parse_due_at(due_raw)
    except ValueError:
        return "Error: due_at must be a valid ISO-8601 timestamp."

    tz_name = ctx.timezone or "UTC"
    local_due = due_at.astimezone(resolve_zone(tz_name))
    rrule: str | None = None
    recurrence = args.get("recurrence")
    if isinstance(recurrence, str) and recurrence.strip():
        mapped = recurrence_to_rrule(recurrence, local_due)
        if mapped is None:
            return ASK_RECURRENCE
        rrule = mapped or None

    now = _now()
    scheduled_for = first_future(due_at, now=now, rrule=rrule, tz_name=tz_name)
    if scheduled_for is None:
        local_label = format_datetime_local(due_at, tz_name)
        return f"That time has already passed ({local_label}). Tell me a future time and I'll set it."

    reminder_id = await ctx.reminders.create(
        ctx.user_id,
        message,
        scheduled_for,
        timezone=tz_name,
        rrule=rrule,
        source="chat",
    )
    if ctx.jobs is not None:
        await ctx.jobs.enqueue(
            kind="reminder_fire",
            user_id=ctx.user_id,
            run_at=scheduled_for,
            payload={
                "reminder_id": reminder_id,
                "occurrence_ts": occurrence_token(scheduled_for),
            },
            dedupe_key=reminder_dedupe_key(reminder_id, scheduled_for),
        )
    local_label = format_datetime_local(scheduled_for, tz_name)
    repeat = f", repeats {rrule}" if rrule else ""
    return f"Reminder {reminder_id} set for {local_label} ({tz_name}){repeat}: {message}"


def set_reminder_tool() -> Tool:
    return Tool(
        name="set_reminder",
        description=(
            "Schedule a reminder at a specific date/time. "
            "Use when the user asks to be reminded, notified, or pinged later. "
            "Requires user approval before it is saved. "
            "recurrence is optional and only one of: daily, weekdays, weekly, monthly."
        ),
        tier=Tier.CONFIRM_REQUIRED,
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What to remind the user about."},
                "due_at": {
                    "type": "string",
                    "description": "When the reminder is due, e.g. 2026-09-22T10:00:00Z",
                },
                "recurrence": {
                    "type": "string",
                    "description": (
                        "Optional repeat: daily, weekdays, weekly, or monthly. "
                        "Omit for a one-time reminder. Do not invent other patterns."
                    ),
                },
            },
            "required": ["message", "due_at"],
        },
        async_run=_run_set_reminder,
    )
