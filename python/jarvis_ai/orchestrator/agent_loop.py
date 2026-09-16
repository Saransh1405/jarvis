"""Agent loop — LLM picks tools, orchestrator runs them, LLM answers."""

from dataclasses import dataclass, field
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn
from jarvis_ai.llm.base import LLMProvider
from jarvis_ai.llm.messages import append_assistant_turn, append_tool_results, initial_messages
from jarvis_ai.policy.decisions import PolicyDecision
from jarvis_ai.policy.engine import PolicyEngine
from jarvis_ai.tools.registry import ToolRegistry

DEFAULT_MAX_TURNS = 5


@dataclass
class PendingAction:
    """A tool call blocked until the user confirms."""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class AgentResult:
    """Final outcome of the agent loop."""

    message: str
    tools_used: list[str] = field(default_factory=list)
    pending_action: PendingAction | None = None


def _policy_denied_message(tool_name: str) -> str:
    return f"Error: tool '{tool_name}' is not allowed by policy."


def _needs_confirm_message(tool_name: str) -> str:
    return (
        f"I need your approval before I can run `{tool_name}`. "
        "Reply with approve to continue once confirmation is supported."
    )


async def run_agent(
    llm: LLMProvider,
    registry: ToolRegistry,
    user_message: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    policy: PolicyEngine | None = None,
    user_id: str | None = None,
) -> AgentResult:
    """
    Run the tool-calling agent loop.

    1. Send user message + tool schemas to LLM
    2. If LLM returns tool_calls → policy check → run via registry → send results back
    3. Repeat until LLM returns final text or max_turns
    """
    engine = policy or PolicyEngine()
    messages = initial_messages(user_message)
    tool_schemas = registry.schemas_for_llm()
    tools_used: list[str] = []

    for _ in range(max_turns):
        turn: AgentTurn = await llm.agent_turn(messages, tool_schemas)

        if turn.wants_tools:
            append_assistant_turn(messages, turn)
            results: list[str] = []
            for call in turn.tool_calls:
                decision = engine.evaluate(registry.get(call.name), call.name, user_id)

                if decision == PolicyDecision.DENY:
                    results.append(_policy_denied_message(call.name))
                    continue

                if decision == PolicyDecision.NEEDS_CONFIRM:
                    return AgentResult(
                        message=_needs_confirm_message(call.name),
                        tools_used=tools_used,
                        pending_action=PendingAction(
                            tool_call_id=call.id,
                            tool_name=call.name,
                            arguments=call.arguments,
                        ),
                    )

                tools_used.append(call.name)
                results.append(registry.run(call.name, call.arguments))

            append_tool_results(messages, turn.tool_calls, results)
            continue

        if turn.text is not None:
            return AgentResult(message=turn.text, tools_used=tools_used)

    return AgentResult(
        message="I could not complete that request.",
        tools_used=tools_used,
    )
