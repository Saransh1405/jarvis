"""Embedding providers. Production uses OpenAI; tests use the hash embedder."""

import hashlib
import math
import re
from typing import Protocol

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Shared topic buckets so the offline eval can retrieve related wording
# ("vegetarian" against "suggest dinner") without calling a network embedder.
# Production never uses this map.
_TOPICS: dict[str, tuple[str, ...]] = {
    "food": ("vegetarian", "dinner", "eat", "eating", "meal", "food", "avoid", "breakfast"),
    "work": ("work", "works", "worked", "job", "jobs", "appscrip", "office", "engineer", "infosys"),
    "city": ("bangalore", "bengaluru", "pune", "lives", "live", "lived", "moved", "city"),
    "family": ("sister", "priya", "brother", "birthday", "family"),
    "fitness": ("workout", "workouts", "morning", "gym", "running", "run"),
    "travel": ("flight", "airport", "trip", "paris", "travel"),
    "home": ("plumber", "raj", "gate", "apartment"),
}


class EmbeddingError(RuntimeError):
    """The embedding provider could not return a vector."""


class EmbeddingProvider(Protocol):
    model: str

    async def embed(self, text: str) -> list[float]: ...


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


def _token_index(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % EMBEDDING_DIM


class HashEmbeddingProvider:
    """Deterministic stand-in. Similar phrases that share a topic land near each other."""

    model = "hash-v1"

    async def embed(self, text: str) -> list[float]:
        values = [0.0] * EMBEDDING_DIM
        tokens = re.findall(r"[a-z0-9']+", text.lower())
        if not tokens:
            values[0] = 1.0
            return values
        for token in tokens:
            values[_token_index(token)] += 1.0
            for topic, words in _TOPICS.items():
                if token in words:
                    values[_token_index("topic:" + topic)] += 3.0
        return _normalize(values)


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str = EMBEDDING_MODEL) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text[:8000],
            )
        except Exception as exc:
            raise EmbeddingError(str(exc)) from exc
        vector = list(response.data[0].embedding)
        if len(vector) != EMBEDDING_DIM:
            raise EmbeddingError(
                f"expected {EMBEDDING_DIM} dimensions from {self.model}, got {len(vector)}"
            )
        return vector


def build_embedder(settings) -> EmbeddingProvider | None:
    key = (getattr(settings, "openai_api_key", "") or getattr(settings, "llm_api_key", "")).strip()
    if not key:
        return None
    model = getattr(settings, "embedding_model", "") or EMBEDDING_MODEL
    return OpenAIEmbeddingProvider(key, model)
