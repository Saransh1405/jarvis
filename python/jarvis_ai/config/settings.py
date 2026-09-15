from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["stub", "openai", "anthropic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    python_api_host: str = "0.0.0.0"
    python_api_port: int = 8000

    # Active LLM vendor: stub | openai | anthropic
    llm_provider: LLMProviderName = "stub"
    # Model for the active provider (leave stub-model to use vendor defaults)
    llm_model: str = "stub-model"
    # Generic fallback key when vendor-specific key is not set
    llm_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_max_tokens: int = Field(default=4096, ge=1, le=200000)

    @property
    def bind_addr(self) -> str:
        return f"{self.python_api_host}:{self.python_api_port}"
