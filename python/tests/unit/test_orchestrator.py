import pytest

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.stub import StubLLMProvider
from jarvis_ai.orchestrator.agent_loop import run_agent
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.orchestrator.routing import try_extract_calculator_expression
from jarvis_ai.tools import build_default_registry


class ScriptedLLM(StubLLMProvider):
    """Test double that returns predetermined agent turns."""

    def __init__(self, turns: list[AgentTurn]) -> None:
        super().__init__()
        self._turns = turns
        self._index = 0

    async def agent_turn(self, messages, tools):
        turn = self._turns[self._index]
        self._index += 1
        return turn


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("calculate 2+2", "2+2"),
        ("calc 99*101", "99*101"),
        ("  CALCULATE  15*0.2  ", "15*0.2"),
        ("99*101", "99*101"),
        ("(10+5)/3", "(10+5)/3"),
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
    result = await run_agent(llm, build_default_registry(), "what is 99 times 101?")
    assert result.message == "99 times 101 is 9,999."
    assert result.tools_used == ["calculator"]


@pytest.mark.asyncio
async def test_orchestrator_llm_picks_calculator_for_natural_language() -> None:
    orch = Orchestrator(llm=StubLLMProvider(), tools=build_default_registry())
    result = await orch.chat("what is 99 times 101?", None)
    assert "9999" in result["message"]
    assert result["tools_used"] == ["calculator"]
    assert result["source"] == "agent:calculator"


@pytest.mark.asyncio
async def test_orchestrator_explicit_calculate_still_works() -> None:
    orch = Orchestrator(llm=StubLLMProvider(), tools=build_default_registry())
    result = await orch.chat("calculate 99*101", None)
    assert "9999" in result["message"]
    assert result["tools_used"] == ["calculator"]


@pytest.mark.asyncio
async def test_orchestrator_falls_back_to_llm() -> None:
    orch = Orchestrator(llm=StubLLMProvider(), tools=build_default_registry())
    result = await orch.chat("hello", None)
    assert result["message"] == "Echo: hello"
    assert result["source"] == "llm"
    assert result["tools_used"] is None


@pytest.mark.asyncio
async def test_orchestrator_stream_after_agent_loop() -> None:
    import json

    orch = Orchestrator(llm=StubLLMProvider(), tools=build_default_registry())
    payloads: list[str] = []
    async for payload in orch.stream_chat("calc 2+2"):
        payloads.append(payload)
    events = [json.loads(p) for p in payloads]
    assert events[-1]["type"] == "done"
    assert events[-1]["tools_used"] == ["calculator"]
    tokens = "".join(e["content"] for e in events if e.get("type") == "token")
    assert "4" in tokens
