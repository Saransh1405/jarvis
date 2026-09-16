import pytest

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.orchestrator.agent_loop import run_agent
from jarvis_ai.policy.decisions import PolicyDecision
from jarvis_ai.policy.engine import PolicyEngine
from jarvis_ai.tools.calculator import calculator_tool
from jarvis_ai.tools.registry import ToolRegistry
from jarvis_ai.tools.save_note import save_note_tool
from tests.conftest import ScriptedLLM


def test_policy_engine_allows_safe_tools() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(calculator_tool(), "calculator")
    assert decision == PolicyDecision.ALLOW


def test_policy_engine_requires_confirm_for_save_note() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(save_note_tool(), "save_note")
    assert decision == PolicyDecision.NEEDS_CONFIRM


def test_policy_engine_denies_unknown_tool() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(None, "does_not_exist")
    assert decision == PolicyDecision.DENY


@pytest.mark.asyncio
async def test_agent_loop_blocks_confirm_required_tool() -> None:
    registry = ToolRegistry()
    registry.register(save_note_tool())

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

    result = await run_agent(llm, registry, "save a note: buy milk")
    assert result.pending_action is not None
    assert result.pending_action.tool_name == "save_note"
    assert result.pending_action.arguments == {"content": "buy milk"}
    assert "approval" in result.message.lower()
    assert result.tools_used == []


@pytest.mark.asyncio
async def test_agent_loop_denies_unknown_tool_via_policy() -> None:
    registry = ToolRegistry()
    registry.register(calculator_tool())

    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(id="call_1", name="ghost_tool", arguments={}),
                ]
            ),
            AgentTurn(text="I could not run that tool."),
        ]
    )

    result = await run_agent(llm, registry, "run ghost tool")
    assert result.pending_action is None
    assert result.message == "I could not run that tool."


@pytest.mark.asyncio
async def test_agent_loop_allows_calculator_through_policy() -> None:
    registry = ToolRegistry()
    registry.register(calculator_tool())

    llm = ScriptedLLM(
        [
            AgentTurn(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "2+2"})
                ]
            ),
            AgentTurn(text="2+2 equals 4."),
        ]
    )

    result = await run_agent(llm, registry, "calculate 2+2")
    assert result.message == "2+2 equals 4."
    assert result.tools_used == ["calculator"]
    assert result.pending_action is None
