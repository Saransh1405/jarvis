from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


async def _run_forget_memory(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to forget a memory."
    if ctx.memory is None:
        return "Error: memory store is not configured."

    memory_id = str(args.get("memory_id") or "").strip()
    query = str(args.get("query") or "").strip()
    if memory_id:
        row = await ctx.memory.get(ctx.user_id, memory_id)
        if row is None:
            return "I couldn't find that memory."
        await ctx.memory.delete(ctx.user_id, memory_id)
        return f"Forgot: {row.content}"
    if not query:
        return "Error: say which memory to forget."

    finder = getattr(ctx.memory, "search_for_forget", None)
    if finder is None:
        matches = await ctx.memory.search(ctx.user_id, query, limit=5)
    else:
        matches = await finder(ctx.user_id, query, limit=5)
    if not matches:
        return "I couldn't find a matching memory."
    forgotten: list[str] = []
    for match in matches:
        await ctx.memory.delete(ctx.user_id, match.id)
        forgotten.append(match.content)
    lines = "\n".join(f"- {content}" for content in forgotten)
    return f"Forgot:\n{lines}"


def forget_memory_tool() -> Tool:
    return Tool(
        name="forget_memory",
        description=(
            "Delete memories that match a query or a specific memory id. "
            "Requires approval. The arguments must name what will be deleted."
        ),
        tier=Tier.CONFIRM_REQUIRED,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to match against stored memories.",
                },
                "memory_id": {
                    "type": "string",
                    "description": "Exact memory id to delete.",
                },
            },
        },
        async_run=_run_forget_memory,
    )
