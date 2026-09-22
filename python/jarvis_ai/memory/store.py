"""Long-term memory — Postgres + trigram search (Graphiti/Neo4j optional later)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg


@dataclass(frozen=True)
class MemoryFact:
    id: str
    user_id: str
    content: str
    source: str
    created_at: datetime


class PostgresMemoryStore:
    """Durable user memory backed by Postgres."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_fact(self, user_id: str, content: str, source: str = "chat") -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO memory_facts (user_id, content, source)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            user_id,
            content,
            source,
        )
        assert row is not None
        return str(row["id"])

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryFact]:
        query = query.strip()
        if not query:
            return await self.recent(user_id, limit=limit)

        rows = await self._pool.fetch(
            """
            SELECT id::text, user_id, content, source, created_at
            FROM memory_facts
            WHERE user_id = $1
              AND content ILIKE '%' || $2 || '%'
            ORDER BY created_at DESC
            LIMIT $3
            """,
            user_id,
            query[:500],
            limit,
        )
        return [_row_to_fact(row) for row in rows]

    async def recent(self, user_id: str, limit: int = 5) -> list[MemoryFact]:
        rows = await self._pool.fetch(
            """
            SELECT id::text, user_id, content, source, created_at
            FROM memory_facts
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_row_to_fact(row) for row in rows]


class InMemoryMemoryStore:
    """Ephemeral memory for unit tests."""

    def __init__(self) -> None:
        self._facts: list[MemoryFact] = []

    async def add_fact(self, user_id: str, content: str, source: str = "chat") -> str:
        fact_id = str(uuid4())
        self._facts.append(
            MemoryFact(
                id=fact_id,
                user_id=user_id,
                content=content,
                source=source,
                created_at=datetime.now(timezone.utc),
            )
        )
        return fact_id

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryFact]:
        query_lower = query.strip().lower()
        matches = [
            f
            for f in self._facts
            if f.user_id == user_id and (not query_lower or query_lower in f.content.lower())
        ]
        matches.sort(key=lambda f: f.created_at, reverse=True)
        return matches[:limit]

    async def recent(self, user_id: str, limit: int = 5) -> list[MemoryFact]:
        facts = [f for f in self._facts if f.user_id == user_id]
        facts.sort(key=lambda f: f.created_at, reverse=True)
        return facts[:limit]


def _row_to_fact(row: asyncpg.Record) -> MemoryFact:
    created_at = row["created_at"]
    if not isinstance(created_at, datetime):
        created_at = datetime.fromisoformat(str(created_at))
    return MemoryFact(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        content=str(row["content"]),
        source=str(row["source"]),
        created_at=created_at,
    )
