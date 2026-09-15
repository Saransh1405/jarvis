"""OpenAI chat completions provider."""

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT, LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions API (streaming + tool calling)."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    def _messages(self, message: str, system: str | None) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system or DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

    async def complete(self, message: str, system: str | None = None) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._messages(message, system),
        )
        content = response.choices[0].message.content
        return content or ""

    async def stream(self, message: str, system: str | None = None) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=self._messages(message, system),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def agent_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentTurn:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools or None,
        )
        message = response.choices[0].message
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for call in message.tool_calls:
                args = json.loads(call.function.arguments or "{}")
                tool_calls.append(
                    ToolCall(
                        id=call.id,
                        name=call.function.name,
                        arguments=args,
                    )
                )
        return AgentTurn(text=message.content, tool_calls=tool_calls)
