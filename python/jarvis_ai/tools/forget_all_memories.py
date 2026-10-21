from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.context import ToolContext


async def _run_forget_all(args: dict[str, Any], ctx: ToolContext) -> str:
    del args
    if not ctx.user_id:
        return "Error: user identity is required to forget memories."
    if ctx.memory is None or not hasattr(ctx.memory, "forget_all"):
        return "Error: memory store is not configured."
    count = await ctx.memory.forget_all(ctx.user_id)
    return f"Forgot everything I had stored ({count})."


def forget_all_memories_tool() -> Tool:
    return Tool(
        name="forget_all_memories",
        description=(
            "Permanently delete every memory stored for this user. "
            "Always ask for confirmation first."
        ),
        tier=Tier.ALWAYS_CONFIRM,
        parameters={"type": "object", "properties": {}},
        async_run=_run_forget_all,
    )
