from typing import Any

import pytest

from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.conversations.history import stored_messages_to_llm
from jarvis_ai.conversations.memory import InMemoryConversationsStore
from jarvis_ai.conversations.models import Message
from jarvis_ai.llm.agent_types import AgentTurn
from jarvis_ai.memory.store import InMemoryMemoryStore
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.reminders.memory import InMemoryRemindersStore
from jarvis_ai.tools import build_default_registry
from tests.conftest import ScriptedLLM


def _assert_openai_tool_message_order(messages: list[dict[str, Any]]) -> None:
    expecting: set[str] | None = None
    for msg in messages:
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            if expecting:
                raise AssertionError("assistant tool_calls before prior tools were answered")
            expecting = {str(tc["id"]) for tc in msg["tool_calls"]}
        elif role == "tool":
            tid = str(msg.get("tool_call_id", ""))
            if not expecting or tid not in expecting:
                raise AssertionError(f"orphan tool message: {tid!r}")
            expecting.discard(tid)
            if not expecting:
                expecting = None
        elif role in ("user", "assistant"):
            if expecting:
                raise AssertionError(f"{role} message before tool results were sent")


def test_stored_messages_to_llm_skips_orphan_tool_rows() -> None:
    history = [
        Message(
            id="1",
            conversation_id="c",
            user_id="u",
            role="user",
            content="hi",
            metadata={},
            created_at=None,
        ),
        Message(
            id="2",
            conversation_id="c",
            user_id="u",
            role="assistant",
            content="Approve please",
            metadata={},
            created_at=None,
        ),
        Message(
            id="3",
            conversation_id="c",
            user_id="u",
            role="tool",
            content="ok",
            metadata={"tool_call_id": "call_x"},
            created_at=None,
        ),
    ]
    llm = stored_messages_to_llm(history, "system")
    roles = [m["role"] for m in llm]
    assert roles == ["system", "user", "assistant"]


@pytest.mark.asyncio
async def test_approve_then_follow_up_has_valid_tool_message_chain() -> None:
    conv_store = InMemoryConversationsStore()

    class ValidatingLLM(ScriptedLLM):
        async def agent_turn(self, messages, tools):
            _assert_openai_tool_message_order(messages)
            return await super().agent_turn(messages, tools)

    llm = ValidatingLLM(
        [
            AgentTurn(text="Reminder is set."),
            AgentTurn(text="Note saved."),
        ]
    )
    orch = Orchestrator(
        llm=llm,
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        memory=InMemoryMemoryStore(),
        pending_actions=InMemoryPendingActionsStore(),
        conversations=conv_store,
    )

    first = await orch.chat("my dentist is on April 12 at 3pm", None, user_id="user-1")
    action_id = first["pending_action"]["action_id"]
    assert action_id

    await orch.approve_action(action_id, "user-1")

    second = await orch.chat(
        "yes save a note",
        first["conversation_id"],
        user_id="user-1",
    )
    assert second["message"]
