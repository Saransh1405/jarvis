"""Tool interface shared by all JARVIS tools."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jarvis_ai.policy.policy import Tier

ToolHandler = Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class Tool:
    """A callable capability the agent can invoke."""

    name: str
    description: str
    tier: Tier
    parameters: dict[str, Any]
    run: ToolHandler

    def to_openai_schema(self) -> dict[str, Any]:
        """JSON schema shape for OpenAI tool-calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """JSON schema shape for Anthropic tool use."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
