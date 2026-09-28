import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

from jarvis_ai.config.settings import Settings
from jarvis_ai.conversations.history import llm_message_to_stored, stored_messages_to_llm
from jarvis_ai.llm.agent_types import ToolCall
from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT, LLMProvider
from jarvis_ai.llm.factory import create_llm_provider
from jarvis_ai.orchestrator.agent_loop import (
    PendingAction,
    resume_agent_after_approval,
    run_agent,
    run_agent_with_messages,
)
from jarvis_ai.policy.engine import PolicyEngine
from jarvis_ai.tools.context import (
    MemoryStore,
    NotesStore,
    PendingActionsStore,
    RemindersStore,
    ToolCallLogStore,
    ToolContext,
)
from jarvis_ai.tools.registry import ToolRegistry, build_default_registry

HISTORY_MESSAGE_LIMIT = 40


class ConversationsStore(Protocol):
    async def create_conversation(self, user_id: str) -> str: ...

    async def get_conversation(self, user_id: str, conversation_id: str) -> Any | None: ...

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    async def list_messages(
        self, user_id: str, conversation_id: str, limit: int = 100
    ) -> list[Any]: ...

    async def list_conversations(self, user_id: str, limit: int = 20) -> list[Any]: ...


class Orchestrator:
    """Chat orchestrator — runs the LLM tool-calling agent loop."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
        tools: ToolRegistry | None = None,
        policy: PolicyEngine | None = None,
        notes: NotesStore | None = None,
        reminders: RemindersStore | None = None,
        memory: MemoryStore | None = None,
        pending_actions: PendingActionsStore | None = None,
        tool_logger: ToolCallLogStore | None = None,
        conversations: ConversationsStore | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._llm = llm or create_llm_provider(self._settings)
        self._tools = tools or build_default_registry()
        self._policy = policy or PolicyEngine()
        self._notes = notes
        self._reminders = reminders
        self._memory = memory
        self._pending_actions = pending_actions
        self._tool_logger = tool_logger
        self._conversations = conversations

    @property
    def llm(self) -> LLMProvider:
        return self._llm

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    @property
    def conversations(self) -> ConversationsStore | None:
        return self._conversations

    def _uses_persistence(self) -> bool:
        return self._conversations is not None

    def _tool_context(self, user_id: str | None) -> ToolContext:
        return ToolContext(
            user_id=user_id,
            notes=self._notes,
            reminders=self._reminders,
            memory=self._memory,
        )

    async def _build_system_prompt(self, user_id: str | None, user_message: str) -> str:
        sections = [DEFAULT_SYSTEM_PROMPT]

        if user_id and self._reminders is not None:
            due = await self._reminders.list_due(user_id)
            if due:
                lines = [f"- {r.message} (due {r.due_at.isoformat()})" for r in due]
                sections.append("Due reminders for this user:\n" + "\n".join(lines))

        if user_id and self._memory is not None:
            facts = await self._memory.search(user_id, user_message, limit=5)
            if facts:
                lines = [f"- ({f.source}) {f.content}" for f in facts]
                sections.append("Relevant long-term memory:\n" + "\n".join(lines))

        return "\n\n".join(sections)

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
            "action_id": pending.action_id,
            "tool_call_id": pending.tool_call_id,
            "tool_name": pending.tool_name,
            "arguments": pending.arguments,
        }

    async def _persist_llm_slice(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[dict[str, Any]],
        start_index: int,
    ) -> None:
        if self._conversations is None:
            return
        for msg in messages[start_index:]:
            role, content, metadata = llm_message_to_stored(msg)
            if role not in ("user", "assistant", "tool"):
                continue
            await self._conversations.append_message(
                user_id, conversation_id, role, content, metadata
            )

    async def _run_chat_agent(
        self,
        message: str,
        conversation_id: str | None,
        user_id: str | None,
    ):
        if not self._uses_persistence():
            conv_id = conversation_id or "conv-stub"
            system_prompt = await self._build_system_prompt(user_id, message)
            result = await run_agent(
                self._llm,
                self._tools,
                message,
                policy=self._policy,
                user_id=user_id,
                tool_ctx=self._tool_context(user_id),
                system_prompt=system_prompt,
                conversation_id=conv_id,
                pending_store=self._pending_actions,
                tool_logger=self._tool_logger,
            )
            return conv_id, result

        if not user_id:
            raise ValueError("user_id required")

        if conversation_id:
            conv = await self._conversations.get_conversation(user_id, conversation_id)
            if conv is None:
                raise LookupError("conversation not found")
            conv_id = conversation_id
        else:
            conv_id = await self._conversations.create_conversation(user_id)

        history = await self._conversations.list_messages(
            user_id, conv_id, limit=HISTORY_MESSAGE_LIMIT
        )
        system_prompt = await self._build_system_prompt(user_id, message)
        llm_messages = stored_messages_to_llm(history, system_prompt)
        await self._conversations.append_message(user_id, conv_id, "user", message)
        llm_messages.append({"role": "user", "content": message})
        agent_start = len(llm_messages)

        result = await run_agent_with_messages(
            self._llm,
            self._tools,
            llm_messages,
            policy=self._policy,
            user_id=user_id,
            tool_ctx=self._tool_context(user_id),
            conversation_id=conv_id,
            pending_store=self._pending_actions,
            tool_logger=self._tool_logger,
        )
        await self._persist_llm_slice(user_id, conv_id, llm_messages, agent_start)
        if result.pending_action is not None:
            await self._conversations.append_message(
                user_id, conv_id, "assistant", result.message
            )
        return conv_id, result

    def _chat_error_response(self, exc: Exception) -> dict:
        if isinstance(exc, ValueError):
            return {"error": str(exc), "status_code": 401}
        if isinstance(exc, LookupError):
            return {"error": str(exc), "status_code": 404}
        raise exc

    async def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        try:
            conv_id, result = await self._run_chat_agent(message, conversation_id, user_id)
        except (ValueError, LookupError) as exc:
            return self._chat_error_response(exc)

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
        try:
            conv_id, result = await self._run_chat_agent(message, conversation_id, user_id)
        except (ValueError, LookupError) as exc:
            err = self._chat_error_response(exc)
            yield json.dumps({"type": "error", "error": err["error"], "status_code": err["status_code"]})
            return

        if result.pending_action is not None:
            yield json.dumps(
                {
                    "type": "confirm_required",
                    "conversation_id": conv_id,
                    "pending_action": self._pending_action_payload(result.pending_action),
                }
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

    async def approve_action(self, action_id: str, user_id: str | None) -> dict:
        if not user_id:
            return {"error": "user_id required", "status_code": 401}
        if self._pending_actions is None:
            return {"error": "pending actions not configured", "status_code": 503}

        record = await self._pending_actions.get_for_user(action_id, user_id)
        if record is None:
            return {"error": "action not found", "status_code": 404}
        if record.status != "pending":
            return {"error": f"action already {record.status}", "status_code": 409}

        approved_call = ToolCall(
            id=record.tool_call_id,
            name=record.tool_name,
            arguments=record.arguments,
        )
        messages = list(record.messages)
        resume_start = len(messages)
        result = await resume_agent_after_approval(
            self._llm,
            self._tools,
            messages,
            approved_call,
            self._tool_context(user_id),
            policy=self._policy,
            pending_store=self._pending_actions,
            conversation_id=record.conversation_id,
            tool_logger=self._tool_logger,
        )
        await self._pending_actions.set_status(action_id, user_id, "executed")

        conv_id = record.conversation_id or "conv-stub"
        if self._conversations is not None and record.conversation_id:
            await self._persist_llm_slice(user_id, record.conversation_id, messages, resume_start)

        return {
            "message": result.message,
            "conversation_id": conv_id,
            "provider": self._llm.name,
            "model": self._llm.model,
            "source": self._source_label(result.tools_used, None),
            "tools_used": result.tools_used or None,
            "action_id": action_id,
            "status": "executed",
        }

    async def reject_action(self, action_id: str, user_id: str | None) -> dict:
        if not user_id:
            return {"error": "user_id required", "status_code": 401}
        if self._pending_actions is None:
            return {"error": "pending actions not configured", "status_code": 503}

        record = await self._pending_actions.get_for_user(action_id, user_id)
        if record is None:
            return {"error": "action not found", "status_code": 404}
        if record.status != "pending":
            return {"error": f"action already {record.status}", "status_code": 409}

        await self._pending_actions.set_status(action_id, user_id, "rejected")
        return {
            "action_id": action_id,
            "status": "rejected",
            "message": f"Cancelled `{record.tool_name}`.",
        }

    async def list_conversations_for_user(self, user_id: str, limit: int = 20) -> list[dict]:
        if self._conversations is None:
            return []
        convs = await self._conversations.list_conversations(user_id, limit=limit)
        return [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in convs
        ]

    async def list_messages_for_user(
        self, user_id: str, conversation_id: str, limit: int = 100
    ) -> list[dict] | None:
        if self._conversations is None:
            return None
        conv = await self._conversations.get_conversation(user_id, conversation_id)
        if conv is None:
            return None
        rows = await self._conversations.list_messages(user_id, conversation_id, limit=limit)
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata": m.metadata,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
