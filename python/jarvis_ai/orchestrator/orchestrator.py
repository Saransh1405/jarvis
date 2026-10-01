import json
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol

from jarvis_ai.config.settings import Settings
from jarvis_ai.conversations.history import (
    apply_pending_confirm_to_messages,
    llm_message_to_stored,
    stored_messages_to_llm,
    tool_calls_metadata_for_pending,
)
from jarvis_ai.memory.extraction import extract_chat_facts
from jarvis_ai.memory.helpers import store_extracted_facts
from jarvis_ai.observability.tool_log import log_agent_tools_summary
from jarvis_ai.llm.agent_types import ToolCall
from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT, LLMProvider
from jarvis_ai.llm.factory import create_llm_provider
from jarvis_ai.orchestrator.agent_loop import (
    AgentResult,
    PendingAction,
    resume_agent_after_approval,
    run_agent,
    run_agent_with_messages,
    _try_calculator_shortcut,
    _try_confirm_tool_shortcut,
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

_MEMORY_STOP_WORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "about",
        "did",
        "you",
        "tell",
        "that",
        "this",
        "have",
        "with",
        "from",
        "your",
        "the",
    }
)


def _memory_search_terms(user_message: str) -> list[str]:
    terms: list[str] = []
    stripped = user_message.strip()
    if stripped:
        terms.append(stripped)
    for word in re.findall(r"[A-Za-z0-9']+", stripped):
        lower = word.lower()
        if len(word) >= 4 and lower not in _MEMORY_STOP_WORDS:
            terms.append(word)
    return terms


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
            facts = []
            seen: set[str] = set()
            for term in _memory_search_terms(user_message):
                for fact in await self._memory.search(user_id, term, limit=5):
                    if fact.id not in seen:
                        seen.add(fact.id)
                        facts.append(fact)
                    if len(facts) >= 5:
                        break
                if len(facts) >= 5:
                    break
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

    async def _capture_chat_memory(
        self,
        user_id: str | None,
        user_message: str,
        result: AgentResult,
    ) -> None:
        if not user_id or self._memory is None:
            return
        if result.pending_action is not None:
            return
        if "remember_fact" in (result.tools_used or []):
            return
        facts = extract_chat_facts(user_message, result.message)
        if not facts:
            return
        await store_extracted_facts(self._memory, user_id, facts, source="chat")

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
            log_agent_tools_summary(user_id, conv_id, result.tools_used)
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
        ctx = self._tool_context(user_id)
        shortcut = await _try_calculator_shortcut(
            message, self._tools, ctx, self._tool_logger
        )
        if shortcut is not None:
            await self._conversations.append_message(
                user_id, conv_id, "assistant", shortcut.message
            )
            log_agent_tools_summary(user_id, conv_id, shortcut.tools_used)
            return conv_id, shortcut

        pending = await _try_confirm_tool_shortcut(
            message,
            llm_messages,
            self._tools,
            ctx,
            self._pending_actions,
            conv_id,
        )
        if pending is not None:
            meta: dict[str, Any] = {}
            if pending.pending_action is not None:
                pa = pending.pending_action
                meta["tool_calls"] = tool_calls_metadata_for_pending(
                    pa.tool_call_id, pa.tool_name, pa.arguments
                )
            await self._conversations.append_message(
                user_id, conv_id, "assistant", pending.message, meta or None
            )
            log_agent_tools_summary(user_id, conv_id, pending.tools_used)
            return conv_id, pending

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
        if result.pending_action is not None:
            apply_pending_confirm_to_messages(llm_messages, result.message)
        await self._persist_llm_slice(user_id, conv_id, llm_messages, agent_start)
        log_agent_tools_summary(user_id, conv_id, result.tools_used)
        return conv_id, result

    def _chat_error_response(self, exc: Exception) -> dict:
        if isinstance(exc, ValueError):
            return {"error": str(exc), "status_code": 401}
        if isinstance(exc, LookupError):
            return {"error": str(exc), "status_code": 404}
        llm_err = self._llm_provider_error(exc)
        if llm_err is not None:
            return llm_err
        raise exc

    @staticmethod
    def _llm_provider_error(exc: Exception) -> dict | None:
        """Map vendor SDK errors to a client-safe chat error payload."""
        try:
            from anthropic import APIError as AnthropicAPIError
        except ImportError:
            AnthropicAPIError = ()  # type: ignore[misc, assignment]

        try:
            from openai import APIError as OpenAIAPIError
        except ImportError:
            OpenAIAPIError = ()  # type: ignore[misc, assignment]

        if isinstance(exc, (OpenAIAPIError, AnthropicAPIError)):
            status = getattr(exc, "status_code", None)
            if not isinstance(status, int) or status < 400 or status > 599:
                status = 502
            return {"error": str(exc), "status_code": status}
        return None

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
        except Exception as exc:
            llm_err = self._llm_provider_error(exc)
            if llm_err is not None:
                return llm_err
            raise

        await self._capture_chat_memory(user_id, message, result)

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
        yield json.dumps({"type": "status", "phase": "thinking"})

        try:
            conv_id, result = await self._run_chat_agent(message, conversation_id, user_id)
        except Exception as exc:
            err = self._chat_error_response(exc)
            yield json.dumps({"type": "error", "error": err["error"], "status_code": err["status_code"]})
            return

        await self._capture_chat_memory(user_id, message, result)

        if result.pending_action is not None:
            yield json.dumps(
                {
                    "type": "confirm_required",
                    "conversation_id": conv_id,
                    "pending_action": self._pending_action_payload(result.pending_action),
                }
            )

        for chunk in re.findall(r"\S+\s*|\n", result.message):
            yield json.dumps({"type": "token", "content": chunk})

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
