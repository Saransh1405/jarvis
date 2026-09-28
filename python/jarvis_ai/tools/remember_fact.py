from typing import Any

from jarvis_ai.memory.helpers import add_fact_if_new, normalize_fact_content
from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


async def _run_remember_fact(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to store memory."
    if ctx.memory is None:
        return "Error: memory store is not configured."

    content = normalize_fact_content(str(args.get("content", "")))
    if not content:
        return "Error: memory content cannot be empty."

    fact_id = await add_fact_if_new(ctx.memory, ctx.user_id, content, source="manual")
    if fact_id is None:
        return "That fact is already stored."
    return f"Remembered fact {fact_id}: {content}"


def remember_fact_tool() -> Tool:
    return Tool(
        name="remember_fact",
        description=(
            "Store a durable fact about the user for long-term recall "
            "(preferences, contacts, household details)."
        ),
        tier=Tier.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact to remember verbatim.",
                }
            },
            "required": ["content"],
        },
        async_run=_run_remember_fact,
    )
