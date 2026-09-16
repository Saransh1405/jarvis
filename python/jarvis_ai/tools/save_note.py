"""Save-note tool — requires user confirmation before execution."""

from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool


def _run_save_note(args: dict[str, Any]) -> str:
    content = str(args.get("content", "")).strip()
    if not content:
        return "Error: note content cannot be empty."
    return f"Saved note: {content}"


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
        run=_run_save_note,
    )
