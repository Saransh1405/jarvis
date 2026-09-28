"""Agent loop — LLM picks tools, orchestrator runs them, LLM answers."""

from dataclasses import dataclass, field
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.base import LLMProvider
from jarvis_ai.llm.messages import append_assistant_turn, append_tool_results, initial_messages
from jarvis_ai.policy.decisions import PolicyDecision
from jarvis_ai.policy.engine import PolicyEngine
from jarvis_ai.tools.context import PendingActionsStore, ToolCallLogStore, ToolContext
from jarvis_ai.tools.registry import ToolRegistry

DEFAULT_MAX_TURNS = 5


@dataclass
class PendingAction:
    """A tool call blocked until the user confirms."""

    action_id: str | None
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


def _needs_confirm_message(tool_name: str, action_id: str | None) -> str:
    if action_id:
        return (
            f"I need your approval before I can run `{tool_name}`. "
            f"Approve action `{action_id}` via POST /api/v1/actions/{action_id}/approve."
        )
    return (
        f"I need your approval before I can run `{tool_name}`. "
        "Authenticate so the action can be stored for approval."
    )


async def _log_tool_call(
    logger: ToolCallLogStore | None,
    ctx: ToolContext,
    tool_name: str,
    arguments: dict[str, Any],
    result: str,
) -> None:
    if logger is None:
        return
    if not ctx.user_id:
        return
    await logger.log(ctx.user_id, tool_name, arguments, result)


async def _agent_loop(
    llm: LLMProvider,
    registry: ToolRegistry,
    messages: list[dict[str, Any]],
    ctx: ToolContext,
    tools_used: list[str],
    max_turns: int,
    policy: PolicyEngine,
    pending_store: PendingActionsStore | None,
    conversation_id: str | None,
    tool_logger: ToolCallLogStore | None,
    policy_override: set[str] | None = None,
) -> AgentResult:
    tool_schemas = registry.schemas_for_llm()
    override = policy_override or set()

    for _ in range(max_turns):
        turn: AgentTurn = await llm.agent_turn(messages, tool_schemas)

        if turn.wants_tools:
            append_assistant_turn(messages, turn)
            results: list[str] = []
            for call in turn.tool_calls:
                skip_policy = call.name in override
                decision = (
                    PolicyDecision.ALLOW
                    if skip_policy
                    else policy.evaluate(registry.get(call.name), call.name, ctx.user_id)
                )

                if decision == PolicyDecision.DENY:
                    results.append(_policy_denied_message(call.name))
                    continue

                if decision == PolicyDecision.NEEDS_CONFIRM:
                    action_id: str | None = None
                    if pending_store is not None and ctx.user_id:
                        action_id = await pending_store.create(
                            user_id=ctx.user_id,
                            tool_call_id=call.id,
                            tool_name=call.name,
                            arguments=call.arguments,
                            messages=messages,
                            conversation_id=conversation_id,
                        )
                    confirm_msg = _needs_confirm_message(call.name, action_id)
                    return AgentResult(
                        message=confirm_msg,
                        tools_used=tools_used,
                        pending_action=PendingAction(
                            action_id=action_id,
                            tool_call_id=call.id,
                            tool_name=call.name,
                            arguments=call.arguments,
                        ),
                    )

                tools_used.append(call.name)
                result = await registry.run(call.name, call.arguments, ctx)
                await _log_tool_call(tool_logger, ctx, call.name, call.arguments, result)
                results.append(result)

            append_tool_results(messages, turn.tool_calls, results)
            continue

        if turn.text is not None:
            messages.append({"role": "assistant", "content": turn.text})
            return AgentResult(message=turn.text, tools_used=tools_used)

    return AgentResult(
        message="I could not complete that request.",
        tools_used=tools_used,
    )


async def run_agent_with_messages(
    llm: LLMProvider,
    registry: ToolRegistry,
    messages: list[dict[str, Any]],
    max_turns: int = DEFAULT_MAX_TURNS,
    policy: PolicyEngine | None = None,
    user_id: str | None = None,
    tool_ctx: ToolContext | None = None,
    conversation_id: str | None = None,
    pending_store: PendingActionsStore | None = None,
    tool_logger: ToolCallLogStore | None = None,
) -> AgentResult:
    """Run the tool-calling loop from an existing message list (includes system + history)."""
    engine = policy or PolicyEngine()
    ctx = tool_ctx or ToolContext(user_id=user_id)
    if user_id and ctx.user_id is None:
        ctx = ToolContext(
            user_id=user_id,
            notes=ctx.notes,
            reminders=ctx.reminders,
            memory=ctx.memory,
        )
    tools_used: list[str] = []
    return await _agent_loop(
        llm,
        registry,
        messages,
        ctx,
        tools_used,
        max_turns,
        engine,
        pending_store,
        conversation_id,
        tool_logger,
    )


async def run_agent(
    llm: LLMProvider,
    registry: ToolRegistry,
    user_message: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    policy: PolicyEngine | None = None,
    user_id: str | None = None,
    tool_ctx: ToolContext | None = None,
    system_prompt: str | None = None,
    conversation_id: str | None = None,
    pending_store: PendingActionsStore | None = None,
    tool_logger: ToolCallLogStore | None = None,
) -> AgentResult:
    """Run the tool-calling agent loop from a new user message."""
    engine = policy or PolicyEngine()
    ctx = tool_ctx or ToolContext(user_id=user_id)
    if user_id and ctx.user_id is None:
        ctx = ToolContext(
            user_id=user_id,
            notes=ctx.notes,
            reminders=ctx.reminders,
            memory=ctx.memory,
        )
    messages = initial_messages(user_message, system=system_prompt)
    tools_used: list[str] = []
    return await _agent_loop(
        llm,
        registry,
        messages,
        ctx,
        tools_used,
        max_turns,
        engine,
        pending_store,
        conversation_id,
        tool_logger,
    )


async def resume_agent_after_approval(
    llm: LLMProvider,
    registry: ToolRegistry,
    messages: list[dict[str, Any]],
    approved_call: ToolCall,
    ctx: ToolContext,
    max_turns: int = DEFAULT_MAX_TURNS,
    policy: PolicyEngine | None = None,
    pending_store: PendingActionsStore | None = None,
    conversation_id: str | None = None,
    tool_logger: ToolCallLogStore | None = None,
) -> AgentResult:
    """Continue the agent loop after a confirm-required tool was approved."""
    engine = policy or PolicyEngine()
    tools_used = [approved_call.name]
    result = await registry.run(approved_call.name, approved_call.arguments, ctx)
    await _log_tool_call(tool_logger, ctx, approved_call.name, approved_call.arguments, result)
    append_tool_results(messages, [approved_call], [result])
    return await _agent_loop(
        llm,
        registry,
        messages,
        ctx,
        tools_used,
        max_turns,
        engine,
        pending_store,
        conversation_id,
        tool_logger,
        policy_override={approved_call.name},
    )
