"""Map stored messages to LLM chat format."""

import json
from typing import Any

from jarvis_ai.conversations.models import Message


def tool_calls_metadata_for_pending(
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments),
            },
        }
    ]


def apply_pending_confirm_to_messages(
    messages: list[dict[str, Any]], confirm_text: str
) -> None:
    """Attach confirm copy to the assistant message that holds pending tool_calls."""
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            msg["content"] = confirm_text
            return


def stored_messages_to_llm(
    history: list[Message],
    system_prompt: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    open_tool_call_ids: set[str] | None = None

    for row in history:
        if row.role == "user":
            open_tool_call_ids = None
            messages.append({"role": "user", "content": row.content})
        elif row.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": row.content}
            tool_calls = row.metadata.get("tool_calls")
            if tool_calls:
                msg["tool_calls"] = tool_calls
                open_tool_call_ids = {
                    str(tc.get("id", "")) for tc in tool_calls if tc.get("id")
                }
            else:
                open_tool_call_ids = None
            messages.append(msg)
        elif row.role == "tool":
            tool_call_id = str(row.metadata.get("tool_call_id", ""))
            if open_tool_call_ids and tool_call_id in open_tool_call_ids:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": row.content,
                    }
                )
                open_tool_call_ids.discard(tool_call_id)
                if not open_tool_call_ids:
                    open_tool_call_ids = None
            # Skip orphan tool rows (e.g. legacy history missing assistant tool_calls).
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
