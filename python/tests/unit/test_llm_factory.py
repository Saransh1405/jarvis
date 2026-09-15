import pytest

from jarvis_ai.config.settings import Settings
from jarvis_ai.llm.factory import LLMProviderError, create_llm_provider, resolve_model
from jarvis_ai.llm.openai_provider import OpenAIProvider
from jarvis_ai.llm.anthropic_provider import AnthropicProvider
from jarvis_ai.llm.stub import StubLLMProvider


def test_resolve_model_uses_default_for_stub():
    assert resolve_model("openai", "stub-model") == "gpt-4o-mini"
    assert resolve_model("anthropic", "stub-model") == "claude-sonnet-4-20250514"


def test_resolve_model_uses_explicit():
    assert resolve_model("openai", "gpt-4o") == "gpt-4o"


def test_factory_stub():
    settings = Settings(llm_provider="stub")
    provider = create_llm_provider(settings)
    assert isinstance(provider, StubLLMProvider)
    assert provider.name == "stub"


def test_factory_openai_requires_key():
    settings = Settings(llm_provider="openai", openai_api_key="", llm_api_key="")
    with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
        create_llm_provider(settings)


def test_factory_openai_with_key():
    settings = Settings(
        llm_provider="openai",
        openai_api_key="sk-test",
        llm_model="gpt-4o-mini",
    )
    provider = create_llm_provider(settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4o-mini"


def test_factory_anthropic_with_fallback_key():
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="",
        llm_api_key="ant-test",
    )
    provider = create_llm_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_factory_unknown_provider():
    settings = Settings(llm_provider="stub")
    settings.llm_provider = "gemini"  # type: ignore[assignment]
    with pytest.raises(LLMProviderError, match="Unknown LLM_PROVIDER"):
        create_llm_provider(settings)


@pytest.mark.asyncio
async def test_stub_complete_and_stream():
    provider = StubLLMProvider()
    assert await provider.complete("hi") == "Echo: hi"
    chunks = [c async for c in provider.stream("hi")]
    assert "".join(chunks) == "Echo: hi"
