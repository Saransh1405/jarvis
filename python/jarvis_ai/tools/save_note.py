"""Save-note tool — requires user confirmation before execution."""

from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


def _require_user(ctx: ToolContext) -> str | None:
    if not ctx.user_id:
        return "Error: user identity is required to save notes (use gateway auth or X-User-ID)."
    if ctx.notes is None:
        return "Error: notes storage is not configured."
    return None


async def _run_save_note(args: dict[str, Any], ctx: ToolContext) -> str:
    err = _require_user(ctx)
    if err:
        return err

    content = str(args.get("content", "")).strip()
    if not content:
        return "Error: note content cannot be empty."

    note_id = await ctx.notes.create(ctx.user_id, content)
    if ctx.memory is not None:
        await ctx.memory.add_fact(ctx.user_id, content, source="note")
    return f"Saved note {note_id}: {content}"


def save_note_tool() -> Tool:
    return Tool(
        name="save_note",
        description="Save a short note for later reference.",
        tier=Tier.CONFIRM_REQUIRED,
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The note text to save.",
                }
            },
            "required": ["content"],
        },
        async_run=_run_save_note,
    )
