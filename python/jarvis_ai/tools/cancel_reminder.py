from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.reminders.actions import cancel_reminder
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


async def _run_cancel_reminder(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to cancel reminders."
    if ctx.reminders is None:
        return "Error: reminders storage is not configured."
    reminder_id = str(args.get("reminder_id", "")).strip()
    if not reminder_id:
        return "Error: reminder_id is required."
    reminder = await ctx.reminders.get_for_user(ctx.user_id, reminder_id)
    if reminder is None:
        return "I couldn't find that reminder."
    return await cancel_reminder(ctx.reminders, ctx.jobs, reminder)


def cancel_reminder_tool() -> Tool:
    return Tool(
        name="cancel_reminder",
        description=(
            "Cancel a scheduled reminder so it will not fire. "
            "Requires user approval. Use the reminder id from list_reminders."
        ),
        tier=Tier.CONFIRM_REQUIRED,
        parameters={
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "Id of the reminder to cancel.",
                }
            },
            "required": ["reminder_id"],
        },
        async_run=_run_cancel_reminder,
    )
