"""Anthropic Messages API provider."""

import json
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT, LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Messages API (streaming + tool use)."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    def _to_anthropic_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", {})
            converted.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    def _split_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        system = DEFAULT_SYSTEM_PROMPT
        anthropic_messages: list[dict[str, Any]] = []

        for item in messages:
            role = item.get("role")
            if role == "system":
                system = str(item.get("content", system))
                continue

            if role == "user":
                anthropic_messages.append(
                    {"role": "user", "content": item.get("content", "")}
                )
                continue

            if role == "assistant":
                content: list[dict[str, Any]] = []
                if item.get("content"):
                    content.append({"type": "text", "text": item["content"]})
                for call in item.get("tool_calls", []):
                    fn = call.get("function", {})
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": fn.get("name", ""),
                            "input": json.loads(fn.get("arguments", "{}")),
                        }
                    )
                anthropic_messages.append({"role": "assistant", "content": content})
                continue

            if role == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": item.get("tool_call_id", ""),
                                "content": item.get("content", ""),
                            }
                        ],
                    }
                )

        return system, anthropic_messages

    async def complete(self, message: str, system: str | None = None) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system or DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "".join(parts)

    async def stream(self, message: str, system: str | None = None) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system or DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def agent_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentTurn:
        system, anthropic_messages = self._split_messages(messages)
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=anthropic_messages,
            tools=self._to_anthropic_tools(tools) if tools else None,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),
                    )
                )

        text = "".join(text_parts) if text_parts else None
        return AgentTurn(text=text, tool_calls=tool_calls)
