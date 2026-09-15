"""LLM provider abstraction — swap vendors via configuration."""

from jarvis_ai.llm.base import DEFAULT_SYSTEM_PROMPT, LLMProvider
from jarvis_ai.llm.factory import create_llm_provider, resolve_model
from jarvis_ai.llm.stub import StubLLMProvider

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "LLMProvider",
    "StubLLMProvider",
    "create_llm_provider",
    "resolve_model",
]
