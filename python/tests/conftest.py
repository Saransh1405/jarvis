"""Pytest configuration — force stub LLM so API tests need no API keys."""

import os

from jarvis_ai.llm.agent_types import AgentTurn
from jarvis_ai.llm.stub import StubLLMProvider

os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("LLM_MODEL", "stub-model")
# Unit tests use in-memory notes. Integration tests use JARVIS_TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = ""
os.environ["POSTGRES_DSN"] = ""


class ScriptedLLM(StubLLMProvider):
    """Test double that returns predetermined agent turns."""

    def __init__(self, turns: list[AgentTurn]) -> None:
        super().__init__()
        self._turns = turns
        self._index = 0

    async def agent_turn(self, messages, tools):
        turn = self._turns[self._index]
        self._index += 1
        return turn


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "integration: tests that need a live DATABASE_URL")
