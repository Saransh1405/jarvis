import pytest

from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.tools import build_default_registry
from tests.conftest import ScriptedLLM


@pytest.mark.asyncio
async def test_save_note_pending_then_approve_persists() -> None:
    llm = ScriptedLLM(
        [
            AgentTurn(text="Done — I saved your note about passport renewal."),
        ]
    )
    orch = Orchestrator(
        llm=llm,
        tools=build_default_registry(),
        notes=InMemoryNotesStore(),
        pending_actions=InMemoryPendingActionsStore(),
    )

    chat = await orch.chat("save a note: passport renewal", None, user_id="user-1")
    assert chat["pending_action"] is not None
    action_id = chat["pending_action"]["action_id"]
    assert action_id

    approved = await orch.approve_action(action_id, "user-1")
    assert "passport" in approved["message"].lower() or approved.get("tools_used")
    assert approved.get("tools_used") == ["save_note"]
