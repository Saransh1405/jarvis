import pytest

from jarvis_ai.policy.policy import Tier
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.tools import ToolNotFoundError, build_default_registry
from jarvis_ai.tools.context import ToolContext


def test_default_registry_has_builtin_tools() -> None:
    registry = build_default_registry()
    assert "calculator" in registry.names()
    assert "get_note" in registry.names()
    assert "save_note" in registry.names()


@pytest.mark.asyncio
async def test_registry_run_calculator() -> None:
    registry = build_default_registry()
    ctx = ToolContext()
    result = await registry.run("calculator", {"expression": "2+2"}, ctx)
    assert result == "4"


@pytest.mark.asyncio
async def test_registry_unknown_tool() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolNotFoundError):
        await registry.run("does_not_exist", {}, ToolContext())


def test_registry_llm_schemas() -> None:
    registry = build_default_registry()
    schemas = registry.schemas_for_llm()
    names = {schema["function"]["name"] for schema in schemas}
    assert names == {
        "calculator",
        "get_note",
        "list_reminders",
        "remember_fact",
        "save_note",
        "search_memory",
        "set_reminder",
    }


EXPECTED_TOOL_TIERS: dict[str, Tier] = {
    "calculator": Tier.SAFE,
    "get_note": Tier.SAFE,
    "list_reminders": Tier.SAFE,
    "remember_fact": Tier.SAFE,
    "search_memory": Tier.SAFE,
    "save_note": Tier.CONFIRM_REQUIRED,
    "set_reminder": Tier.CONFIRM_REQUIRED,
}


def test_default_registry_tiers_match_v2() -> None:
    registry = build_default_registry()
    for name, expected_tier in EXPECTED_TOOL_TIERS.items():
        tool = registry.get(name)
        assert tool is not None, name
        assert tool.tier == expected_tier, name
    assert set(registry.names()) == set(EXPECTED_TOOL_TIERS.keys())


@pytest.mark.asyncio
async def test_save_and_get_note_in_memory() -> None:
    registry = build_default_registry()
    store = InMemoryNotesStore()
    ctx = ToolContext(user_id="user-test", notes=store)

    saved = await registry.run("save_note", {"content": "buy milk"}, ctx)
    assert saved.startswith("Saved note ")

    listed = await registry.run("get_note", {}, ctx)
    assert "buy milk" in listed
