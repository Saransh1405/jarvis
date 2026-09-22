from datetime import datetime, timezone
from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


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

    reminder_id = await ctx.reminders.create(ctx.user_id, message, due_at)
    return f"Reminder {reminder_id} set for {due_at.isoformat()}: {message}"


def set_reminder_tool() -> Tool:
    return Tool(
        name="set_reminder",
        description="Schedule a reminder at a specific date/time (ISO-8601 due_at).",
        tier=Tier.CONFIRM_REQUIRED,
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What to remind the user about."},
                "due_at": {
                    "type": "string",
                    "description": "When the reminder is due, e.g. 2026-09-22T10:00:00Z",
                },
            },
            "required": ["message", "due_at"],
        },
        async_run=_run_set_reminder,
    )
