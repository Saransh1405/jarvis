"""Types for the LLM agent / tool-calling loop."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """One tool the LLM wants to invoke."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentTurn:
    """One LLM response turn — either text, tool calls, or both."""

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return len(self.tool_calls) > 0
