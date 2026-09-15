"""Stub LLM for local dev and automated tests (no API key required)."""

import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT, LLMProvider
from jarvis_ai.orchestrator.routing import try_extract_calculator_expression

_TIMES_PATTERN = re.compile(r"(\d+)\s+times\s+(\d+)", re.IGNORECASE)
_WHAT_IS_PATTERN = re.compile(r"what is (.+)\??$", re.IGNORECASE)


def _last_user_message(messages: list[dict[str, Any]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            return item["content"]
    return ""


def _last_tool_result(messages: list[dict[str, Any]]) -> str | None:
    for item in reversed(messages):
        if item.get("role") == "tool" and isinstance(item.get("content"), str):
            return item["content"]
    return None


def _infer_calculator_expression(message: str) -> str | None:
    direct = try_extract_calculator_expression(message)
    if direct:
        return direct

    times_match = _TIMES_PATTERN.search(message)
    if times_match:
        return f"{times_match.group(1)}*{times_match.group(2)}"

    what_match = _WHAT_IS_PATTERN.match(message.strip())
    if what_match:
        inner = what_match.group(1).strip()
        inner_expr = try_extract_calculator_expression(inner)
        if inner_expr:
            return inner_expr
        if re.fullmatch(r"[\d\s+\-*/().]+", inner):
            return inner

    return None


class StubLLMProvider(LLMProvider):
    """Echo provider with basic tool-calling simulation for tests."""

    def __init__(self, model: str = "stub-model") -> None:
        self._model = model

    @property
    def name(self) -> str:
        return "stub"

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, message: str, system: str | None = None) -> str:
        _ = system or DEFAULT_SYSTEM_PROMPT
        return f"Echo: {message}"

    async def stream(self, message: str, system: str | None = None) -> AsyncIterator[str]:
        text = await self.complete(message, system)
        for char in text:
            yield char

    async def agent_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentTurn:
        tool_result = _last_tool_result(messages)
        if tool_result is not None:
            return AgentTurn(text=f"The answer is {tool_result}.")

        user_message = _last_user_message(messages)
        expression = _infer_calculator_expression(user_message)
        if expression and tools:
            return AgentTurn(
                tool_calls=[
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="calculator",
                        arguments={"expression": expression},
                    )
                ]
            )

        return AgentTurn(text=f"Echo: {user_message}")
