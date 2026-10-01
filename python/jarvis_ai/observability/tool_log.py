"""Persist tool invocations for auditing and emit structured logs."""

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_RESULT_LOG_MAX = 240
_ARGS_LOG_MAX = 500


def _preview(text: str, limit: int) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 3] + "..."


def log_tool_executed(
    user_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    result: str,
) -> None:
    """INFO log when a tool runs successfully (shows in API / docker compose logs)."""
    args_json = _preview(json.dumps(arguments, default=str), _ARGS_LOG_MAX)
    logger.info(
        "tool_executed user_id=%s tool=%s args=%s result_preview=%s",
        user_id or "-",
        tool_name,
        args_json,
        _preview(result, _RESULT_LOG_MAX),
    )


def log_tool_policy_denied(user_id: str | None, tool_name: str) -> None:
    logger.warning(
        "tool_denied user_id=%s tool=%s",
        user_id or "-",
        tool_name,
    )


def log_tool_confirm_required(
    user_id: str | None,
    tool_name: str,
    action_id: str | None,
) -> None:
    logger.info(
        "tool_confirm_required user_id=%s tool=%s action_id=%s",
        user_id or "-",
        tool_name,
        action_id or "-",
    )


def log_agent_tools_summary(
    user_id: str | None,
    conversation_id: str | None,
    tools_used: list[str],
) -> None:
    if not tools_used:
        logger.info(
            "agent_no_tools user_id=%s conversation_id=%s",
            user_id or "-",
            conversation_id or "-",
        )
        return
    logger.info(
        "agent_tools_used user_id=%s conversation_id=%s tools=%s",
        user_id or "-",
        conversation_id or "-",
        ",".join(tools_used),
    )


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
        log_tool_executed(user_id, tool_name, arguments, result)
        if not user_id:
            logger.warning(
                "tool_call_db skipped: missing user_id tool=%s",
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
        log_tool_executed(user_id, tool_name, arguments, result)


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
        log_tool_executed(user_id, tool_name, arguments, result)
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
