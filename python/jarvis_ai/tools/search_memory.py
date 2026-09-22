from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


async def _run_search_memory(args: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.user_id:
        return "Error: user identity is required to search memory."
    if ctx.memory is None:
        return "Error: memory store is not configured."

    query = str(args.get("query", "")).strip()
    limit = int(args.get("limit", 5))
    limit = max(1, min(limit, 20))
    facts = await ctx.memory.search(ctx.user_id, query, limit=limit)
    if not facts:
        return "No matching memories found."
    lines = [f"- ({f.source}) {f.content}" for f in facts]
    return "Memories:\n" + "\n".join(lines)


def search_memory_tool() -> Tool:
    return Tool(
        name="search_memory",
        description="Search long-term memory for facts the user shared earlier.",
        tier=Tier.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
                "limit": {"type": "integer", "description": "Max results (default 5)."},
            },
            "required": ["query"],
        },
        async_run=_run_search_memory,
    )
