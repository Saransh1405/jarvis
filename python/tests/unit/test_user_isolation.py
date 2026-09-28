import pytest

from datetime import datetime, timezone

from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.memory.store import InMemoryMemoryStore
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.reminders.memory import InMemoryRemindersStore
from jarvis_ai.tools import build_default_registry
from jarvis_ai.tools.context import ToolContext
from tests.conftest import ScriptedLLM


@pytest.mark.asyncio
async def test_notes_isolated_between_users() -> None:
    registry = build_default_registry()
    notes = InMemoryNotesStore()
    ctx_a = ToolContext(user_id="user-a", notes=notes)
    ctx_b = ToolContext(user_id="user-b", notes=notes)

    await registry.run("save_note", {"content": "secret-a"}, ctx_a)

    listed_b = await registry.run("get_note", {}, ctx_b)
    assert "secret-a" not in listed_b
    assert "No notes" in listed_b or "no saved notes" in listed_b.lower()


@pytest.mark.asyncio
async def test_memory_search_isolated_between_users() -> None:
    registry = build_default_registry()
    memory = InMemoryMemoryStore()
    await memory.add_fact("user-a", "gate code 9999", source="chat")

    ctx_b = ToolContext(user_id="user-b", memory=memory)
    result = await registry.run("search_memory", {"query": "gate"}, ctx_b)
    assert "9999" not in result


@pytest.mark.asyncio
async def test_reminders_isolated_between_users() -> None:
    registry = build_default_registry()
    reminders = InMemoryRemindersStore()
    ctx_a = ToolContext(user_id="user-a", reminders=reminders)
    ctx_b = ToolContext(user_id="user-b", reminders=reminders)

    await reminders.create(
        "user-a",
        "call plumber",
        due_at=datetime.now(timezone.utc),
    )
    listed_b = await registry.run("list_reminders", {}, ctx_b)
    assert "plumber" not in listed_b


@pytest.mark.asyncio
async def test_user_b_cannot_approve_user_a_pending_action() -> None:
    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="save_note",
                        arguments={"content": "private"},
                    )
                ]
            ),
        ]
    )
    pending = InMemoryPendingActionsStore()
    orch = Orchestrator(
        llm=llm,
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        pending_actions=pending,
    )
    chat = await orch.chat("save note private", None, user_id="user-a")
    action_id = chat["pending_action"]["action_id"]

    blocked = await orch.approve_action(action_id, "user-b")
    assert blocked.get("status_code") == 404
