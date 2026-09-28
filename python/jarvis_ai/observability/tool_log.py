"""Persist tool invocations for auditing."""

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


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
        if not user_id:
            logger.warning(
                "tool_call_log skipped: missing user_id tool=%s",
                tool_name,
            )
            return
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


class InMemoryToolCallLogger:
    """Records tool invocations for unit tests."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def log(
        self,
        user_id: str | None,
        tool_name: str,
        arguments: dict[str, Any],
        result: str,
    ) -> None:
        if not user_id:
            return
        self.entries.append(
            {
                "user_id": user_id,
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "result": result,
            }
        )
