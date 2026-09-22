"""Get-note tool — read saved notes for the current user."""

from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


def _require_user(ctx: ToolContext) -> str | None:
    if not ctx.user_id:
        return "Error: user identity is required to read notes (use gateway auth or X-User-ID)."
    if ctx.notes is None:
        return "Error: notes storage is not configured."
    return None


async def _run_get_note(args: dict[str, Any], ctx: ToolContext) -> str:
    err = _require_user(ctx)
    if err:
        return err

    note_id = args.get("note_id")
    if note_id is not None:
        note_id = str(note_id).strip()
        if not note_id:
            return "Error: note_id cannot be empty."
        note = await ctx.notes.get_for_user(ctx.user_id, note_id)
        if note is None:
            return f"Error: no note found with id {note_id}."
        return f"[{note.id}] {note.content}"

    limit = int(args.get("limit", 10))
    limit = max(1, min(limit, 50))
    notes = await ctx.notes.list_recent(ctx.user_id, limit=limit)
    if not notes:
        return "You have no saved notes."
    lines = [f"[{n.id}] {n.content}" for n in notes]
    return "Recent notes:\n" + "\n".join(lines)


def get_note_tool() -> Tool:
    return Tool(
        name="get_note",
        description=(
            "Retrieve saved notes. Pass note_id for one note, or omit note_id to list recent notes."
        ),
        tier=Tier.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "string",
                    "description": "UUID of a specific note to fetch.",
                },
                "limit": {
                    "type": "integer",
                    "description": "When listing, max notes to return (default 10).",
                },
            },
        },
        async_run=_run_get_note,
    )
