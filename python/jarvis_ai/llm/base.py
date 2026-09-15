"""LLM provider interface — all vendors implement this contract."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from jarvis_ai.llm.agent_types import AgentTurn

DEFAULT_SYSTEM_PROMPT = (
    "You are JARVIS, a helpful personal AI assistant. "
    "Be concise, accurate, and conversational. "
    "Use tools when they help answer accurately (e.g. calculator for math)."
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
