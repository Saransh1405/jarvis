from datetime import datetime, timezone
from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.reminders.actions import snooze_reminder
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


def _now() -> datetime:
    return datetime.now(timezone.utc)


_KINDS = {
    "10": "s10",
    "10m": "s10",
    "s10": "s10",
    "60": "s60",
    "60m": "s60",
    "1h": "s60",
    "s60": "s60",
    "tomorrow": "st",
    "st": "st",
}


async def _run_snooze_reminder(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to snooze reminders."
    if ctx.reminders is None:
        return "Error: reminders storage is not configured."
    reminder_id = str(args.get("reminder_id", "")).strip()
    if not reminder_id:
        return "Error: reminder_id is required."
    reminder = await ctx.reminders.get_for_user(ctx.user_id, reminder_id)
    if reminder is None:
        return "I couldn't find that reminder."

    kind = _resolve_kind(args)
    if kind is None:
        return "Error: snooze must be 10 minutes, 1 hour, or tomorrow."
    return await snooze_reminder(
        ctx.reminders,
        ctx.jobs,
        reminder,
        kind=kind,
        now=_now(),
    )


def _resolve_kind(args: dict[str, Any]) -> str | None:
    raw = args.get("until")
    if isinstance(raw, str) and raw.strip():
        return _KINDS.get(raw.strip().lower())
    minutes = args.get("minutes")
    if minutes in (10, "10"):
        return "s10"
    if minutes in (60, "60"):
        return "s60"
    return None


def snooze_reminder_tool() -> Tool:
    return Tool(
        name="snooze_reminder",
        description=(
            "Snooze one of the user's reminders by 10 minutes, 1 hour, or until tomorrow "
            "at the same local time."
        ),
        tier=Tier.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "Id of the reminder to snooze."},
                "minutes": {
                    "type": "integer",
                    "description": "10 or 60. Omit when using until.",
                },
                "until": {
                    "type": "string",
                    "description": "10m, 1h, or tomorrow.",
                },
            },
            "required": ["reminder_id"],
        },
        async_run=_run_snooze_reminder,
    )
