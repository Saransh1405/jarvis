"""Map stored messages to LLM chat format."""

from typing import Any

from jarvis_ai.conversations.models import Message


def stored_messages_to_llm(
    history: list[Message],
    system_prompt: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for row in history:
        if row.role == "user":
            messages.append({"role": "user", "content": row.content})
        elif row.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": row.content}
            tool_calls = row.metadata.get("tool_calls")
            if tool_calls:
                msg["tool_calls"] = tool_calls
            messages.append(msg)
        elif row.role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": row.metadata.get("tool_call_id", ""),
                    "content": row.content,
                }
            )
    return messages


def llm_message_to_stored(msg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    role = str(msg.get("role", ""))
    content = str(msg.get("content") or "")
    metadata: dict[str, Any] = {}
    if role == "assistant" and msg.get("tool_calls"):
        metadata["tool_calls"] = msg["tool_calls"]
    if role == "tool":
        metadata["tool_call_id"] = msg.get("tool_call_id", "")
    return role, content, metadata
