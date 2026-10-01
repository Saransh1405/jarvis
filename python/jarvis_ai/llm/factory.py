"""Factory — select LLM provider from application settings."""

from jarvis_ai.config.settings import Settings
from jarvis_ai.llm.anthropic_provider import AnthropicProvider
from jarvis_ai.llm.base import LLMProvider
from jarvis_ai.llm.gemini_provider import GeminiProvider
from jarvis_ai.llm.openai_provider import OpenAIProvider
from jarvis_ai.llm.stub import StubLLMProvider

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "stub": "stub-model",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-3.8-flash",
}


class LLMProviderError(ValueError):
    """Raised when provider configuration is invalid."""


def resolve_model(provider: str, configured_model: str) -> str:
    """Pick model: explicit LLM_MODEL, else provider default."""
    normalized = configured_model.strip()
    if normalized and normalized != "stub-model":
        return normalized
    return _PROVIDER_DEFAULT_MODELS.get(provider, configured_model)


def create_llm_provider(settings: Settings) -> LLMProvider:
    """
    Build the active LLM provider from settings.

    Set LLM_PROVIDER to `stub`, `openai`, `anthropic`, or `gemini`.
    API keys: OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY, or LLM_API_KEY.
    Optional LLM_BASE_URL for OpenAI-compatible proxies (OpenRouter, xAI).
    """
    provider = settings.llm_provider.strip().lower()
    model = resolve_model(provider, settings.llm_model)
    base_url = settings.llm_base_url.strip() or None

    if provider == "stub":
        return StubLLMProvider(model=model)

    if provider == "openai":
        api_key = settings.openai_api_key or settings.llm_api_key
        if not api_key:
            raise LLMProviderError(
                "OpenAI provider requires OPENAI_API_KEY or LLM_API_KEY"
            )
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)

    if provider == "gemini":
        api_key = settings.gemini_api_key or settings.llm_api_key
        if not api_key:
            raise LLMProviderError(
                "Gemini provider requires GEMINI_API_KEY or LLM_API_KEY"
            )
        return GeminiProvider(api_key=api_key, model=model, base_url=base_url)

    if provider == "anthropic":
        api_key = settings.anthropic_api_key or settings.llm_api_key
        if not api_key:
            raise LLMProviderError(
                "Anthropic provider requires ANTHROPIC_API_KEY or LLM_API_KEY"
            )
        return AnthropicProvider(
            api_key=api_key,
            model=model,
            max_tokens=settings.llm_max_tokens,
        )

    raise LLMProviderError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. "
        "Use stub, openai, anthropic, or gemini."
    )
