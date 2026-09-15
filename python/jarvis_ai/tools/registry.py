"""Tool registration and execution."""

from typing import Any

from jarvis_ai.tools.base import Tool
from jarvis_ai.tools.calculator import calculator_tool


class ToolNotFoundError(KeyError):
    """Raised when an unknown tool name is requested."""


class ToolRegistry:
    """Registry of tools the agent can invoke."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def run(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool.run(args)

    def schemas_for_llm(self) -> list[dict[str, Any]]:
        """OpenAI-compatible tool definitions for the agent loop (Phase 2.4)."""
        return [tool.to_openai_schema() for tool in self.list_tools()]


def build_default_registry() -> ToolRegistry:
    """Registry with all built-in Phase 2 starter tools."""
    registry = ToolRegistry()
    registry.register(calculator_tool())
    return registry
