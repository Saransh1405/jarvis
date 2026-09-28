import pytest

from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.observability.tool_log import InMemoryToolCallLogger
from jarvis_ai.orchestrator.agent_loop import run_agent, resume_agent_after_approval
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.tools import build_default_registry
from jarvis_ai.tools.context import ToolContext
from tests.conftest import ScriptedLLM


@pytest.mark.asyncio
async def test_calculator_logs_distinct_user_ids() -> None:
    registry = build_default_registry()
    logger = InMemoryToolCallLogger()
    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"})
                ]
            ),
            AgentTurn(text="2"),
        ]
    )

    await run_agent(
        llm,
        registry,
        "calc",
        user_id="user-a",
        tool_ctx=ToolContext(user_id="user-a"),
        tool_logger=logger,
    )
    await run_agent(
        ScriptedLLM(
            [
                AgentTurn(
                    tool_calls=[
                        ToolCall(id="c2", name="calculator", arguments={"expression": "2+2"})
                    ]
                ),
                AgentTurn(text="4"),
            ]
        ),
        registry,
        "calc",
        user_id="user-b",
        tool_ctx=ToolContext(user_id="user-b"),
        tool_logger=logger,
    )

    assert len(logger.entries) == 2
    assert {e["user_id"] for e in logger.entries} == {"user-a", "user-b"}
    assert all(e["tool_name"] == "calculator" for e in logger.entries)


@pytest.mark.asyncio
async def test_approve_path_logs_executed_tool_with_user_id() -> None:
    registry = build_default_registry()
    logger = InMemoryToolCallLogger()
    notes = InMemoryNotesStore()
    pending = InMemoryPendingActionsStore()
    ctx = ToolContext(user_id="user-1", notes=notes)

    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(id="call_1", name="save_note", arguments={"content": "audit me"})
                ]
            ),
            AgentTurn(text="Saved."),
        ]
    )
    first = await run_agent(
        llm,
        registry,
        "save",
        user_id="user-1",
        tool_ctx=ctx,
        pending_store=pending,
        conversation_id="conv-1",
        tool_logger=logger,
    )
    assert first.pending_action is not None
    action_id = first.pending_action.action_id
    assert action_id

    record = await pending.get_for_user(action_id, "user-1")
    assert record is not None
    approved_call = ToolCall(
        id=record.tool_call_id,
        name=record.tool_name,
        arguments=record.arguments,
    )
    await resume_agent_after_approval(
        ScriptedLLM([AgentTurn(text="Saved.")]),
        registry,
        list(record.messages),
        approved_call,
        ctx,
        pending_store=pending,
        conversation_id="conv-1",
        tool_logger=logger,
    )

    save_logs = [e for e in logger.entries if e["tool_name"] == "save_note"]
    assert len(save_logs) == 1
    assert save_logs[0]["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_tool_logger_skips_missing_user_id() -> None:
    logger = InMemoryToolCallLogger()
    await logger.log(None, "calculator", {"expression": "1+1"}, "2")
    assert logger.entries == []


@pytest.mark.asyncio
async def test_orchestrator_stub_calculator_audit_via_gateway_contract() -> None:
    """Simulates two gateway users chatting with stub LLM; audit rows differ by user_id."""
    from jarvis_ai.llm.stub import StubLLMProvider

    logger = InMemoryToolCallLogger()
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        tool_logger=logger,
    )
    await orch.chat("what is 99 times 101?", None, user_id="gateway-user-1")
    await orch.chat("calculate 99*101", None, user_id="gateway-user-2")

    assert len(logger.entries) >= 2
    user_ids = {e["user_id"] for e in logger.entries}
    assert "gateway-user-1" in user_ids
    assert "gateway-user-2" in user_ids
