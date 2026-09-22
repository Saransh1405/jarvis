"""Persist tool invocations for auditing."""

import json
from typing import Any

import asyncpg


class ToolCallLogger:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def log(
        self,
        user_id: str | None,
        tool_name: str,
        arguments: dict[str, Any],
        result: str,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO tool_call_logs (user_id, tool_name, arguments, result)
            VALUES ($1, $2, $3::jsonb, $4)
            """,
            user_id,
            tool_name,
            json.dumps(arguments),
            result[:8000],
        )


class NoOpToolCallLogger:
    async def log(
        self,
        user_id: str | None,
        tool_name: str,
        arguments: dict[str, Any],
        result: str,
    ) -> None:
        return None
