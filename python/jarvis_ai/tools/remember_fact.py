from datetime import datetime, timezone
from typing import Any

from jarvis_ai.memory.filters import is_secret
from jarvis_ai.memory.helpers import add_fact_if_new, normalize_fact_content
from jarvis_ai.memory.store import KINDS
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
    if is_secret(content):
        return "I won't store passwords, keys, or card numbers."

    kind = str(args.get("kind") or "fact")
    if kind not in KINDS:
        kind = "fact"
    fact_id = await add_fact_if_new(ctx.memory, ctx.user_id, content, source="explicit", kind=kind)
    if fact_id is None:
        return "That fact is already stored."

    row = await ctx.memory.get(ctx.user_id, fact_id) if hasattr(ctx.memory, "get") else None
    embedder = getattr(ctx.memory, "embedder", None)
    if (
        embedder is not None
        and ctx.jobs is not None
        and row is not None
        and row.embedding is None
    ):
        await ctx.jobs.enqueue(
            kind="memory_embed",
            user_id=ctx.user_id,
            run_at=datetime.now(timezone.utc),
            payload={"memory_id": fact_id},
            dedupe_key=f"memory_embed:{fact_id}",
        )
        return (
            f"Remembered fact {fact_id}: {content} "
            "It will be searchable shortly."
        )
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
                },
                "kind": {
                    "type": "string",
                    "enum": ["fact", "preference", "person", "goal", "episode"],
                    "description": "What kind of memory this is. Defaults to fact.",
                },
            },
            "required": ["content"],
        },
        async_run=_run_remember_fact,
    )
