import json
from collections.abc import AsyncIterator

from jarvis_ai.config.settings import Settings
from jarvis_ai.llm.base import LLMProvider
from jarvis_ai.llm.factory import create_llm_provider
from jarvis_ai.orchestrator.agent_loop import PendingAction, run_agent
from jarvis_ai.policy.engine import PolicyEngine
from jarvis_ai.tools.registry import ToolRegistry, build_default_registry


class Orchestrator:
    """Chat orchestrator — runs the LLM tool-calling agent loop."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
        tools: ToolRegistry | None = None,
        policy: PolicyEngine | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._llm = llm or create_llm_provider(self._settings)
        self._tools = tools or build_default_registry()
        self._policy = policy or PolicyEngine()

    @property
    def llm(self) -> LLMProvider:
        return self._llm

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    def _conversation_id(self, conversation_id: str | None) -> str:
        return conversation_id or "conv-stub"

    def _source_label(self, tools_used: list[str], pending: PendingAction | None) -> str:
        if pending is not None:
            return f"policy:pending:{pending.tool_name}"
        if tools_used:
            return f"agent:{','.join(tools_used)}"
        return "llm"

    def _pending_action_payload(self, pending: PendingAction | None) -> dict | None:
        if pending is None:
            return None
        return {
            "tool_call_id": pending.tool_call_id,
            "tool_name": pending.tool_name,
            "arguments": pending.arguments,
        }

    async def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        conv_id = self._conversation_id(conversation_id)
        result = await run_agent(
            self._llm,
            self._tools,
            message,
            policy=self._policy,
            user_id=user_id,
        )

        return {
            "message": result.message,
            "conversation_id": conv_id,
            "provider": self._llm.name,
            "model": self._llm.model,
            "source": self._source_label(result.tools_used, result.pending_action),
            "tools_used": result.tools_used or None,
            "pending_action": self._pending_action_payload(result.pending_action),
        }

    async def stream_chat(
        self,
        message: str,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[str]:
        conv_id = self._conversation_id(conversation_id)
        result = await run_agent(
            self._llm,
            self._tools,
            message,
            policy=self._policy,
            user_id=user_id,
        )

        for char in result.message:
            yield json.dumps({"type": "token", "content": char})

        yield json.dumps(
            {
                "type": "done",
                "conversation_id": conv_id,
                "provider": self._llm.name,
                "model": self._llm.model,
                "source": self._source_label(result.tools_used, result.pending_action),
                "tools_used": result.tools_used or None,
                "pending_action": self._pending_action_payload(result.pending_action),
            }
        )
