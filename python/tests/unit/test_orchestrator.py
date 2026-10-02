import pytest

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.stub import StubLLMProvider
from jarvis_ai.orchestrator.agent_loop import run_agent
from tests.conftest import ScriptedLLM
from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.conversations.memory import InMemoryConversationsStore
from jarvis_ai.memory.store import InMemoryMemoryStore
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.reminders.memory import InMemoryRemindersStore
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.orchestrator.routing import (
    try_extract_calculator_expression,
    try_extract_set_reminder_args,
)
from jarvis_ai.tools import build_default_registry


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("calculate 2+2", "2+2"),
        ("calc 99*101", "99*101"),
        ("  CALCULATE  15*0.2  ", "15*0.2"),
        ("99*101", "99*101"),
        ("(10+5)/3", "(10+5)/3"),
        ("What is 847 times 293?", "847*293"),
        ("847 times 293", "847*293"),
    ],
)
def test_try_extract_calculator_expression_matches(message: str, expected: str) -> None:
    assert try_extract_calculator_expression(message) == expected


@pytest.mark.parametrize(
    "message",
    ["hello", "", "   "],
)
def test_try_extract_calculator_expression_no_match(message: str) -> None:
    assert try_extract_calculator_expression(message) is None


def test_try_extract_set_reminder_dentist_appointment() -> None:
    args = try_extract_set_reminder_args("my dentist is on April 12 at 3pm", timezone_name="UTC")
    assert args is not None
    assert args["message"] == "Dentist appointment"
    assert args["due_at"].endswith("Z")
    assert "T15:00:00" in args["due_at"]


@pytest.mark.asyncio
async def test_orchestrator_reminder_shortcut_pending_without_llm() -> None:
    class FailIfCalledLLM(StubLLMProvider):
        async def agent_turn(self, messages, tools):
            raise AssertionError("LLM must not run for reminder routing shortcut")

    orch = Orchestrator(
        llm=FailIfCalledLLM(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    result = await orch.chat("my dentist is on April 12 at 3pm", None, user_id="user-1")
    assert result["pending_action"]["tool_name"] == "set_reminder"
    assert result["pending_action"]["action_id"]
    assert result["source"] == "policy:pending:set_reminder"
    assert "Approve" in result["message"]


@pytest.mark.asyncio
async def test_stream_reminder_shortcut_emits_confirm_required() -> None:
    import json

    class FailIfCalledLLM(StubLLMProvider):
        async def agent_turn(self, messages, tools):
            raise AssertionError("LLM must not run for reminder routing shortcut")

    orch = Orchestrator(
        llm=FailIfCalledLLM(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    events: list[dict] = []
    async for payload in orch.stream_chat(
        "my dentist is on April 12 at 3pm", user_id="user-1"
    ):
        events.append(json.loads(payload))

    assert any(e.get("type") == "confirm_required" for e in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["pending_action"]["tool_name"] == "set_reminder"
    assert done["source"] == "policy:pending:set_reminder"


@pytest.mark.asyncio
async def test_agent_loop_calls_calculator_then_answers() -> None:
    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "99*101"})
                ]
            ),
            AgentTurn(text="99 times 101 is 9,999."),
        ]
    )
    result = await run_agent(
        llm,
        build_default_registry(),
        "what is 99 times 101 without calc?",
    )
    assert result.message == "99 times 101 is 9,999."
    assert result.tools_used == ["calculator"]


@pytest.mark.asyncio
async def test_orchestrator_llm_picks_calculator_for_natural_language() -> None:
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        memory=InMemoryMemoryStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    result = await orch.chat("what is 99 times 101?", None)
    assert "9999" in result["message"]
    assert result["tools_used"] == ["calculator"]
    assert result["source"] == "agent:calculator"


@pytest.mark.asyncio
async def test_orchestrator_explicit_calculate_still_works() -> None:
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        memory=InMemoryMemoryStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    result = await orch.chat("calculate 99*101", None)
    assert "9999" in result["message"]
    assert result["tools_used"] == ["calculator"]


@pytest.mark.asyncio
async def test_orchestrator_falls_back_to_llm() -> None:
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        memory=InMemoryMemoryStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    result = await orch.chat("hello", None)
    assert result["message"] == "Echo: hello"
    assert result["source"] == "llm"
    assert result["tools_used"] is None


@pytest.mark.asyncio
async def test_orchestrator_blocks_save_note_pending_confirmation() -> None:
    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="save_note",
                        arguments={"content": "buy milk"},
                    )
                ]
            ),
        ]
    )
    orch = Orchestrator(
        llm=llm,
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    result = await orch.chat("save a note: buy milk", None, user_id="user-1")
    assert result["pending_action"]["tool_name"] == "save_note"
    assert result["pending_action"]["action_id"]
    assert result["source"] == "policy:pending:save_note"
    assert result["tools_used"] is None


@pytest.mark.asyncio
async def test_orchestrator_stream_after_agent_loop() -> None:
    import json

    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        memory=InMemoryMemoryStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )
    payloads: list[str] = []
    async for payload in orch.stream_chat("calc 2+2"):
        payloads.append(payload)
    events = [json.loads(p) for p in payloads]
    assert events[-1]["type"] == "done"
    assert events[-1]["tools_used"] == ["calculator"]
    tokens = "".join(e["content"] for e in events if e.get("type") == "token")
    assert "4" in tokens


class TurnCountingLLM(StubLLMProvider):
    """Asserts message history length grows on follow-up turns."""

    def __init__(self) -> None:
        super().__init__()
        self._calls = 0

    async def agent_turn(self, messages, tools):
        self._calls += 1
        if self._calls == 1:
            assert len(messages) == 2
            return AgentTurn(text="First reply")
        assert len(messages) >= 4
        user_lines = [m["content"] for m in messages if m.get("role") == "user"]
        assert "first question" in user_lines[0]
        assert "second question" in user_lines[-1]
        return AgentTurn(text="Second reply")


@pytest.mark.asyncio
async def test_orchestrator_persists_multi_turn_history() -> None:
    conv_store = InMemoryConversationsStore()
    orch = Orchestrator(
        llm=TurnCountingLLM(),
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        pending_actions=InMemoryPendingActionsStore(),
        conversations=conv_store,
    )
    first = await orch.chat("first question", None, user_id="user-1")
    assert first["conversation_id"] != "conv-stub"
    second = await orch.chat(
        "second question",
        first["conversation_id"],
        user_id="user-1",
    )
    assert second["message"] == "Second reply"
    stored = await conv_store.list_messages("user-1", first["conversation_id"])
    roles = [m.role for m in stored]
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


@pytest.mark.asyncio
async def test_orchestrator_conversation_isolation() -> None:
    conv_store = InMemoryConversationsStore()
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        conversations=conv_store,
    )
    first = await orch.chat("hello", None, user_id="user-a")
    blocked = await orch.chat("hello", first["conversation_id"], user_id="user-b")
    assert blocked.get("status_code") == 404
