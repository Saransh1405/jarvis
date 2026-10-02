"""LLM provider interface — all vendors implement this contract."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn

DEFAULT_SYSTEM_PROMPT = (
    "You are JARVIS, a helpful personal AI assistant. "
    "Be concise, accurate, and conversational. "
    "Use tools when they help answer accurately. "
    "For arithmetic (including 'what is X times Y'), always use the calculator tool—do not mental math."
    "When the user asks to save a note, use save_note. "
    "When they ask to be reminded at a specific date or time, use set_reminder with "
    "message and due_at as ISO-8601 UTC. Interpret dates and times in the user's "
    "timezone from the user context block (convert to UTC for due_at). "
    "Do not claim a note or reminder was saved until the user approves the action in the app. "
    "Do not use remember_fact for timed reminders; use set_reminder instead."
)


class LLMProvider(ABC):
    """Vendor-agnostic LLM boundary used by the orchestrator."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (stub, openai, anthropic)."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Active model name for this provider instance."""

    @abstractmethod
    async def complete(self, message: str, system: str | None = None) -> str:
        """Return the full model response for a single user message."""

    @abstractmethod
    async def stream(self, message: str, system: str | None = None) -> AsyncIterator[str]:
        """Yield incremental text deltas as the model generates them."""

    @abstractmethod
    async def agent_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentTurn:
        """One turn of the tool-calling agent loop."""
