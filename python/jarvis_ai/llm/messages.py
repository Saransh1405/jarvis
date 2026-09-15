"""Helpers for building LLM conversation messages."""

import json
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT


def initial_messages(user_message: str, system: str | None = None) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": system or DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def append_assistant_turn(messages: list[dict[str, Any]], turn: AgentTurn) -> None:
    """Record the assistant message (and optional tool calls) in OpenAI-style format."""
    if turn.wants_tools:
        messages.append(
            {
                "role": "assistant",
                "content": turn.text,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in turn.tool_calls
                ],
            }
        )
        return

    messages.append({"role": "assistant", "content": turn.text or ""})


def append_tool_results(
    messages: list[dict[str, Any]], tool_calls: list[ToolCall], results: list[str]
) -> None:
    for call, result in zip(tool_calls, results, strict=True):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            }
        )
