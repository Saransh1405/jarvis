import pytest

from jarvis_ai.user_settings.memory import InMemoryUserSettingsStore

@pytest.mark.asyncio
async def test_in_memory_user_settings_defaults() -> None:
    store = InMemoryUserSettingsStore()
    s = await store.get("user-1")
    assert s.timezone == "UTC"
    assert s.brief_enabled is True


@pytest.mark.asyncio
async def test_orchestrator_system_prompt_includes_user_context() -> None:
    from jarvis_ai.orchestrator.orchestrator import Orchestrator
    from jarvis_ai.user_settings.memory import InMemoryUserSettingsStore

    store = InMemoryUserSettingsStore()
    orch = Orchestrator(user_settings=store)
    prompt = await orch._build_system_prompt("user-1", "hello")
    assert "User context:" in prompt
    assert "timezone: UTC" in prompt
