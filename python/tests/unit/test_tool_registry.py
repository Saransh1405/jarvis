import pytest

from jarvis_ai.tools import ToolNotFoundError, build_default_registry


def test_default_registry_has_builtin_tools() -> None:
    registry = build_default_registry()
    assert "calculator" in registry.names()
    assert "save_note" in registry.names()


def test_registry_run_calculator() -> None:
    registry = build_default_registry()
    result = registry.run("calculator", {"expression": "2+2"})
    assert result == "4"


def test_registry_unknown_tool() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolNotFoundError):
        registry.run("does_not_exist", {})


def test_registry_llm_schemas() -> None:
    registry = build_default_registry()
    schemas = registry.schemas_for_llm()
    names = {schema["function"]["name"] for schema in schemas}
    assert names == {"calculator", "save_note"}
