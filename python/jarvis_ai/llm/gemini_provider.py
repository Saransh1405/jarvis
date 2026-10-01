"""Google Gemini via OpenAI-compatible Chat Completions API."""

import json
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.openai_provider import OpenAIProvider

# https://ai.google.dev/gemini-api/docs/openai
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

# Gemini 3 validates thought_signature on tool round-trips; see thought-signatures docs.
_SKIP_SIGNATURE = "skip_thought_signature_validator"


def _thought_signature_present(tool_calls: list[dict[str, Any]]) -> bool:
    if not tool_calls:
        return True
    extra = tool_calls[0].get("extra_content") or {}
    google = extra.get("google") or {}
    sig = google.get("thought_signature")
    return isinstance(sig, str) and bool(sig.strip())


def _inject_skip_thought_signature(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tool_calls:
        return tool_calls
    first = dict(tool_calls[0])
    extra = dict(first.get("extra_content") or {})
    google = dict(extra.get("google") or {})
    google["thought_signature"] = _SKIP_SIGNATURE
    extra["google"] = google
    first["extra_content"] = extra
    return [first, *tool_calls[1:]]


def _tool_call_payloads_from_response(message: Any, choice_dump: dict[str, Any]) -> list[dict[str, Any]]:
    raw = (choice_dump.get("message") or {}).get("tool_calls") or []
    if raw:
        return [dict(item) for item in raw]

    payloads: list[dict[str, Any]] = []
    for call in message.tool_calls or []:
        payloads.append(call.model_dump(mode="json", exclude_none=True))
    return payloads


def _prepare_messages_for_gemini(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure assistant tool_calls include thought_signature when Gemini requires it."""
    prepared: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            prepared.append(msg)
            continue
        calls = [dict(c) for c in msg["tool_calls"]]
        if not _thought_signature_present(calls):
            calls = _inject_skip_thought_signature(calls)
        prepared.append({**msg, "tool_calls": calls})
    return prepared


class GeminiProvider(OpenAIProvider):
    """Gemini models using the OpenAI-compatible endpoint (tools + streaming)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or DEFAULT_GEMINI_BASE_URL,
            provider_label="gemini",
        )

    async def agent_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentTurn:
        api_messages = _prepare_messages_for_gemini(messages)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            tools=tools or None,
        )
        message = response.choices[0].message
        choice_dump = response.choices[0].model_dump(mode="json")
        payloads = _tool_call_payloads_from_response(message, choice_dump)
        if payloads and not _thought_signature_present(payloads):
            payloads = _inject_skip_thought_signature(payloads)

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

        return AgentTurn(
            text=message.content,
            tool_calls=tool_calls,
            tool_call_payloads=payloads,
        )
