from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


async def _run_list_reminders(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to list reminders."
    if ctx.reminders is None:
        return "Error: reminders storage is not configured."

    include_done = bool(args.get("include_done", False))
    items = await ctx.reminders.list_for_user(ctx.user_id, include_done=include_done)
    if not items:
        return "No reminders found."
    lines = [f"[{r.id}] due {r.due_at.isoformat()} — {r.message}" for r in items]
    return "Reminders:\n" + "\n".join(lines)


def list_reminders_tool() -> Tool:
    return Tool(
        name="list_reminders",
        description="List scheduled reminders for the current user.",
        tier=Tier.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "description": "Include completed reminders.",
                }
            },
        },
        async_run=_run_list_reminders,
    )
