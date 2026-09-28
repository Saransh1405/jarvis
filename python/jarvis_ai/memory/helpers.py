"""Shared limits and deduplicated fact storage."""

from typing import Any, Protocol

MAX_FACT_LENGTH = 500
MAX_FACTS_PER_TURN = 3


class _MemoryWriter(Protocol):
    async def add_fact(self, user_id: str, content: str, source: str = "chat") -> str: ...

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[Any]: ...


def normalize_fact_content(content: str) -> str:
    return content.strip()[:MAX_FACT_LENGTH]


async def add_fact_if_new(
    store: _MemoryWriter,
    user_id: str,
    content: str,
    source: str = "chat",
) -> str | None:
    """Insert a fact unless a very similar one already exists for this user."""
    normalized = normalize_fact_content(content)
    if not normalized or not user_id:
        return None

    needle = normalized.lower()
    candidates = await store.search(user_id, normalized[:80], limit=20)
    for fact in candidates:
        existing = getattr(fact, "content", str(fact)).lower()
        if existing == needle or needle in existing or existing in needle:
            return None

    return await store.add_fact(user_id, normalized, source)


async def store_extracted_facts(
    store: _MemoryWriter,
    user_id: str,
    facts: list[str],
    source: str = "chat",
) -> int:
    stored = 0
    for fact in facts[:MAX_FACTS_PER_TURN]:
        if await add_fact_if_new(store, user_id, fact, source=source):
            stored += 1
    return stored
