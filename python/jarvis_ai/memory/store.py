"""Long-term memory. Keyword search remains; semantic search uses pgvector when embeddings exist."""

import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg

from jarvis_ai.memory.embeddings import EMBEDDING_DIM
from jarvis_ai.memory.rank import select_memories

logger = logging.getLogger(__name__)

KINDS = frozenset({"fact", "preference", "person", "goal", "episode"})
_MEMORY_STOP_WORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "about",
        "did",
        "you",
        "tell",
        "that",
        "this",
        "have",
        "with",
        "from",
        "your",
        "the",
    }
)
_ACTIVE = """
deleted_at IS NULL
AND superseded_by IS NULL
AND (expires_at IS NULL OR expires_at > NOW())
"""


@dataclass(frozen=True)
class MemoryFact:
    id: str
    user_id: str
    content: str
    source: str
    created_at: datetime
    kind: str = "fact"
    importance: int = 3
    confidence: float = 0.8
    embedding: tuple[float, ...] | None = None
    embedding_model: str | None = None
    similarity: float = 0.0
    superseded_by: str | None = None
    deleted_at: datetime | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None
    access_count: int = 0
    last_accessed_at: datetime | None = None


def _vector_literal(values: list[float] | tuple[float, ...] | None) -> str | None:
    if values is None:
        return None
    return "[" + ",".join(format(float(value), ".6f") for value in values) + "]"


def _clamp_importance(value: int) -> int:
    return max(1, min(int(value), 5))


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _kind(value: str) -> str:
    if value in KINDS:
        return value
    return "fact"


def _is_active(fact: MemoryFact, now: datetime | None = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    if fact.deleted_at is not None or fact.superseded_by:
        return False
    if fact.expires_at is not None and fact.expires_at <= moment:
        return False
    return True


def _cosine(left: tuple[float, ...] | list[float], right: tuple[float, ...] | list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / ((left_norm ** 0.5) * (right_norm ** 0.5))


def _search_terms(query: str) -> list[str]:
    terms: list[str] = []
    stripped = query.strip()
    if stripped:
        terms.append(stripped[:500])
    for word in re.findall(r"[A-Za-z0-9']+", stripped):
        if len(word) >= 4 and word.lower() not in _MEMORY_STOP_WORDS:
            terms.append(word)
    return terms


class PostgresMemoryStore:
    """Durable user memory backed by the memories table."""

    def __init__(self, pool: asyncpg.Pool, embedder=None) -> None:
        self._pool = pool
        self._embedder = embedder

    @property
    def embedder(self):
        return self._embedder

    async def add_fact(self, user_id: str, content: str, source: str = "chat") -> str:
        fact_id, _embedded = await self.add(user_id, content, source=source)
        return fact_id

    async def add(
        self,
        user_id: str,
        content: str,
        *,
        source: str = "chat",
        kind: str = "fact",
        importance: int = 3,
        confidence: float = 0.8,
        embedding: list[float] | tuple[float, ...] | None = None,
        embedding_model: str | None = None,
        expires_at: datetime | None = None,
        embed: bool = True,
    ) -> tuple[str, bool]:
        vector = list(embedding) if embedding is not None else None
        model = embedding_model
        embedded = vector is not None
        if vector is None and embed and self._embedder is not None:
            try:
                vector = list(await self._embedder.embed(content))
                model = model or getattr(self._embedder, "model", None)
                embedded = True
            except Exception:
                logger.warning("embedding failed for user %s; memory saved without a vector", user_id)
                embedded = False
        if vector is not None and len(vector) != EMBEDDING_DIM:
            raise ValueError(f"embedding must have {EMBEDDING_DIM} dimensions")
        row = await self._pool.fetchrow(
            """
            INSERT INTO memories (
                user_id, kind, content, embedding, embedding_model,
                importance, confidence, source, expires_at
            )
            VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8, $9)
            RETURNING id::text
            """,
            user_id,
            _kind(kind),
            content,
            _vector_literal(vector),
            model,
            _clamp_importance(importance),
            _clamp_confidence(confidence),
            source,
            expires_at,
        )
        assert row is not None
        return str(row["id"]), embedded

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryFact]:
        query = query.strip()
        if not query:
            return await self.recent(user_id, limit=limit)
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS}
            FROM memories
            WHERE user_id = $1
              AND {_ACTIVE}
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
            f"""
            SELECT {_COLUMNS}
            FROM memories
            WHERE user_id = $1 AND {_ACTIVE}
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_row_to_fact(row) for row in rows]

    async def search_semantic(
        self, user_id: str, vector: list[float] | tuple[float, ...], limit: int = 20
    ) -> list[MemoryFact]:
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS},
                   1 - (embedding <=> $2::vector) AS similarity
            FROM memories
            WHERE user_id = $1
              AND embedding IS NOT NULL
              AND {_ACTIVE}
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            user_id,
            _vector_literal(vector),
            limit,
        )
        return [_row_to_fact(row) for row in rows]

    async def list_preferences(self, user_id: str, limit: int = 3) -> list[MemoryFact]:
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS}
            FROM memories
            WHERE user_id = $1
              AND kind = 'preference'
              AND importance >= 4
              AND {_ACTIVE}
            ORDER BY importance DESC, updated_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_row_to_fact(row) for row in rows]

    async def retrieve_for_prompt(
        self,
        user_id: str,
        query: str,
        *,
        previous: str = "",
        limit: int = 8,
    ) -> list[MemoryFact]:
        text = query.strip()
        if previous and len(text.split()) < 8:
            text = f"{previous}\n{text}"
        if self._embedder is not None and text:
            try:
                vector = await self._embedder.embed(text)
                hits = await self.search_semantic(user_id, vector, limit=20)
                prefs = await self.list_preferences(user_id, limit=3)
                return select_memories(hits, prefs, limit=limit)
            except Exception:
                logger.exception("semantic retrieval failed; falling back to keywords")
        return await self._keyword_retrieve(user_id, query, limit=limit)

    async def search_for_forget(self, user_id: str, query: str, limit: int = 5) -> list[MemoryFact]:
        """Match memories to delete. Does not pin unrelated preferences."""
        text = query.strip()
        if self._embedder is not None and text:
            try:
                vector = await self._embedder.embed(text)
                hits = await self.search_semantic(user_id, vector, limit=20)
                matched = [fact for fact in hits if fact.similarity >= 0.55]
                return matched[:limit]
            except Exception:
                logger.exception("forget search fell back to keywords")
        return await self.search(user_id, text, limit=limit)

    async def _keyword_retrieve(self, user_id: str, query: str, limit: int = 8) -> list[MemoryFact]:
        found: list[MemoryFact] = []
        seen: set[str] = set()
        for pref in await self.list_preferences(user_id, limit=3):
            seen.add(pref.id)
            found.append(pref)
        for term in _search_terms(query):
            for fact in await self.search(user_id, term, limit=limit):
                if fact.id in seen:
                    continue
                seen.add(fact.id)
                found.append(fact)
                if len(found) >= limit:
                    return found
        return found

    async def list(
        self,
        user_id: str,
        *,
        kind: str | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryFact]:
        needle = query.strip() if query else ""
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS}
            FROM memories
            WHERE user_id = $1
              AND {_ACTIVE}
              AND ($2::text IS NULL OR kind = $2)
              AND ($3::text = '' OR content ILIKE '%' || $3 || '%')
            ORDER BY updated_at DESC
            LIMIT $4 OFFSET $5
            """,
            user_id,
            kind if kind in KINDS else None,
            needle,
            limit,
            offset,
        )
        return [_row_to_fact(row) for row in rows]

    async def get(self, user_id: str, memory_id: str) -> MemoryFact | None:
        row = await self._pool.fetchrow(
            f"""
            SELECT {_COLUMNS}
            FROM memories
            WHERE user_id = $1 AND id = $2::uuid AND deleted_at IS NULL
            """,
            user_id,
            memory_id,
        )
        if row is None:
            return None
        return _row_to_fact(row)

    async def update_content(self, user_id: str, memory_id: str, content: str) -> str:
        current = await self.get(user_id, memory_id)
        if current is None or current.superseded_by:
            return "missing"
        if self._embedder is None:
            status = await self._pool.execute(
                """
                UPDATE memories
                SET content = $3, updated_at = NOW()
                WHERE user_id = $1 AND id = $2::uuid AND deleted_at IS NULL
                """,
                user_id,
                memory_id,
                content,
            )
            return "updated" if status.endswith("1") else "missing"
        vector = None
        model = None
        embedded = False
        try:
            vector = list(await self._embedder.embed(content))
            model = getattr(self._embedder, "model", None)
            embedded = True
        except Exception:
            logger.warning("re-embed failed for memory %s", memory_id)
        status = await self._pool.execute(
            """
            UPDATE memories
            SET content = $3,
                embedding = $4::vector,
                embedding_model = $5,
                updated_at = NOW()
            WHERE user_id = $1 AND id = $2::uuid AND deleted_at IS NULL
            """,
            user_id,
            memory_id,
            content,
            _vector_literal(vector),
            model,
        )
        if not status.endswith("1"):
            return "missing"
        return "updated" if embedded else "pending_embed"

    async def delete(self, user_id: str, memory_id: str) -> bool:
        status = await self._pool.execute(
            """
            DELETE FROM memories
            WHERE user_id = $1 AND id = $2::uuid
            """,
            user_id,
            memory_id,
        )
        return status.endswith("1")

    async def forget_all(self, user_id: str) -> int:
        status = await self._pool.execute(
            "DELETE FROM memories WHERE user_id = $1",
            user_id,
        )
        parts = status.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0

    async def touch(self, user_id: str, memory_id: str) -> None:
        await self._pool.execute(
            """
            UPDATE memories
            SET updated_at = NOW(), access_count = access_count + 1
            WHERE user_id = $1 AND id = $2::uuid AND deleted_at IS NULL
            """,
            user_id,
            memory_id,
        )

    async def supersede(self, user_id: str, old_id: str, new_id: str) -> bool:
        status = await self._pool.execute(
            """
            UPDATE memories
            SET superseded_by = $3::uuid, updated_at = NOW()
            WHERE user_id = $1 AND id = $2::uuid AND deleted_at IS NULL
            """,
            user_id,
            old_id,
            new_id,
        )
        return status.endswith("1")

    async def set_embedding(
        self,
        user_id: str,
        memory_id: str,
        vector: list[float],
        model: str,
    ) -> bool:
        status = await self._pool.execute(
            """
            UPDATE memories
            SET embedding = $3::vector, embedding_model = $4, updated_at = NOW()
            WHERE user_id = $1 AND id = $2::uuid AND deleted_at IS NULL
            """,
            user_id,
            memory_id,
            _vector_literal(vector),
            model,
        )
        return status.endswith("1")

    async def mark_accessed(self, user_id: str, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        await self._pool.execute(
            """
            UPDATE memories
            SET last_accessed_at = NOW(), access_count = access_count + 1
            WHERE user_id = $1 AND id = ANY($2::uuid[])
            """,
            user_id,
            memory_ids,
        )

    async def list_unembedded(self, limit: int = 50) -> list[tuple[str, str]]:
        rows = await self._pool.fetch(
            """
            SELECT id::text, user_id
            FROM memories
            WHERE embedding IS NULL AND deleted_at IS NULL AND superseded_by IS NULL
            ORDER BY created_at
            LIMIT $1
            """,
            limit,
        )
        return [(str(row["id"]), str(row["user_id"])) for row in rows]


_COLUMNS = """
id::text, user_id, content, source, created_at, kind, importance, confidence,
embedding_model, superseded_by::text, expires_at, updated_at, access_count, last_accessed_at
"""


def _row_to_fact(row: asyncpg.Record) -> MemoryFact:
    created_at = row["created_at"]
    if not isinstance(created_at, datetime):
        created_at = datetime.fromisoformat(str(created_at))
    similarity = row["similarity"] if "similarity" in row.keys() else 0.0
    return MemoryFact(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        content=str(row["content"]),
        source=str(row["source"]),
        created_at=created_at,
        kind=str(row["kind"]),
        importance=int(row["importance"]),
        confidence=float(row["confidence"]),
        embedding_model=row["embedding_model"],
        similarity=float(similarity or 0.0),
        superseded_by=row["superseded_by"],
        expires_at=row["expires_at"],
        updated_at=row["updated_at"],
        access_count=int(row["access_count"] or 0),
        last_accessed_at=row["last_accessed_at"],
    )


class InMemoryMemoryStore:
    """Ephemeral memory for unit tests."""

    def __init__(self, embedder=None) -> None:
        self._facts: list[MemoryFact] = []
        self._embedder = embedder

    @property
    def embedder(self):
        return self._embedder

    async def add_fact(self, user_id: str, content: str, source: str = "chat") -> str:
        fact_id, _embedded = await self.add(user_id, content, source=source)
        return fact_id

    async def add(
        self,
        user_id: str,
        content: str,
        *,
        source: str = "chat",
        kind: str = "fact",
        importance: int = 3,
        confidence: float = 0.8,
        embedding: list[float] | tuple[float, ...] | None = None,
        embedding_model: str | None = None,
        expires_at: datetime | None = None,
        embed: bool = True,
    ) -> tuple[str, bool]:
        vector = tuple(embedding) if embedding is not None else None
        model = embedding_model
        embedded = vector is not None
        if vector is None and embed and self._embedder is not None:
            try:
                vector = tuple(await self._embedder.embed(content))
                model = model or getattr(self._embedder, "model", None)
                embedded = True
            except Exception:
                embedded = False
        now = datetime.now(timezone.utc)
        fact_id = str(uuid4())
        self._facts.append(
            MemoryFact(
                id=fact_id,
                user_id=user_id,
                content=content,
                source=source,
                created_at=now,
                kind=_kind(kind),
                importance=_clamp_importance(importance),
                confidence=_clamp_confidence(confidence),
                embedding=vector,
                embedding_model=model,
                expires_at=expires_at,
                updated_at=now,
            )
        )
        return fact_id, embedded

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryFact]:
        query_lower = query.strip().lower()
        if not query_lower:
            return await self.recent(user_id, limit=limit)
        matches = [
            fact
            for fact in self._facts
            if fact.user_id == user_id
            and _is_active(fact)
            and query_lower in fact.content.lower()
        ]
        matches.sort(key=lambda fact: fact.created_at, reverse=True)
        return matches[:limit]

    async def recent(self, user_id: str, limit: int = 5) -> list[MemoryFact]:
        facts = [fact for fact in self._facts if fact.user_id == user_id and _is_active(fact)]
        facts.sort(key=lambda fact: fact.created_at, reverse=True)
        return facts[:limit]

    async def search_semantic(
        self, user_id: str, vector: list[float] | tuple[float, ...], limit: int = 20
    ) -> list[MemoryFact]:
        scored: list[MemoryFact] = []
        for fact in self._facts:
            if fact.user_id != user_id or not _is_active(fact) or fact.embedding is None:
                continue
            scored.append(replace(fact, similarity=_cosine(fact.embedding, vector)))
        scored.sort(key=lambda fact: fact.similarity, reverse=True)
        return scored[:limit]

    async def list_preferences(self, user_id: str, limit: int = 3) -> list[MemoryFact]:
        facts = [
            fact
            for fact in self._facts
            if fact.user_id == user_id
            and fact.kind == "preference"
            and fact.importance >= 4
            and _is_active(fact)
        ]
        facts.sort(key=lambda fact: (fact.importance, fact.updated_at or fact.created_at), reverse=True)
        return facts[:limit]

    async def retrieve_for_prompt(
        self,
        user_id: str,
        query: str,
        *,
        previous: str = "",
        limit: int = 8,
    ) -> list[MemoryFact]:
        text = query.strip()
        if previous and len(text.split()) < 8:
            text = f"{previous}\n{text}"
        if self._embedder is not None and text:
            try:
                vector = await self._embedder.embed(text)
                hits = await self.search_semantic(user_id, vector, limit=20)
                prefs = await self.list_preferences(user_id, limit=3)
                return select_memories(hits, prefs, limit=limit)
            except Exception:
                logger.exception("semantic retrieval failed; falling back to keywords")
        return await self._keyword_retrieve(user_id, query, limit=limit)

    async def search_for_forget(self, user_id: str, query: str, limit: int = 5) -> list[MemoryFact]:
        """Match memories to delete. Does not pin unrelated preferences."""
        text = query.strip()
        if self._embedder is not None and text:
            try:
                vector = await self._embedder.embed(text)
                hits = await self.search_semantic(user_id, vector, limit=20)
                matched = [fact for fact in hits if fact.similarity >= 0.55]
                return matched[:limit]
            except Exception:
                logger.exception("forget search fell back to keywords")
        return await self.search(user_id, text, limit=limit)

    async def _keyword_retrieve(self, user_id: str, query: str, limit: int = 8) -> list[MemoryFact]:
        found: list[MemoryFact] = []
        seen: set[str] = set()
        for pref in await self.list_preferences(user_id, limit=3):
            seen.add(pref.id)
            found.append(pref)
        for term in _search_terms(query):
            for fact in await self.search(user_id, term, limit=limit):
                if fact.id in seen:
                    continue
                seen.add(fact.id)
                found.append(fact)
                if len(found) >= limit:
                    return found
        return found

    async def list(
        self,
        user_id: str,
        *,
        kind: str | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryFact]:
        needle = (query or "").strip().lower()
        facts = [
            fact
            for fact in self._facts
            if fact.user_id == user_id
            and _is_active(fact)
            and (not kind or fact.kind == kind)
            and (not needle or needle in fact.content.lower())
        ]
        facts.sort(key=lambda fact: fact.updated_at or fact.created_at, reverse=True)
        return facts[offset : offset + limit]

    async def get(self, user_id: str, memory_id: str) -> MemoryFact | None:
        for fact in self._facts:
            if fact.id == memory_id and fact.user_id == user_id and fact.deleted_at is None:
                return fact
        return None

    async def update_content(self, user_id: str, memory_id: str, content: str) -> str:
        current = await self.get(user_id, memory_id)
        if current is None or current.superseded_by:
            return "missing"
        if self._embedder is None:
            self._replace(memory_id, content=content, updated_at=datetime.now(timezone.utc))
            return "updated"
        vector = None
        model = None
        embedded = False
        try:
            vector = tuple(await self._embedder.embed(content))
            model = getattr(self._embedder, "model", None)
            embedded = True
        except Exception:
            embedded = False
        self._replace(
            memory_id,
            content=content,
            embedding=vector,
            embedding_model=model,
            updated_at=datetime.now(timezone.utc),
        )
        return "updated" if embedded else "pending_embed"

    async def delete(self, user_id: str, memory_id: str) -> bool:
        before = len(self._facts)
        self._facts = [
            fact
            for fact in self._facts
            if not (fact.id == memory_id and fact.user_id == user_id)
        ]
        return len(self._facts) != before

    async def forget_all(self, user_id: str) -> int:
        before = len(self._facts)
        self._facts = [fact for fact in self._facts if fact.user_id != user_id]
        return before - len(self._facts)

    async def touch(self, user_id: str, memory_id: str) -> None:
        fact = await self.get(user_id, memory_id)
        if fact is None:
            return
        self._replace(
            memory_id,
            updated_at=datetime.now(timezone.utc),
            access_count=fact.access_count + 1,
        )

    async def supersede(self, user_id: str, old_id: str, new_id: str) -> bool:
        fact = await self.get(user_id, old_id)
        if fact is None:
            return False
        self._replace(old_id, superseded_by=new_id, updated_at=datetime.now(timezone.utc))
        return True

    async def set_embedding(
        self,
        user_id: str,
        memory_id: str,
        vector: list[float],
        model: str,
    ) -> bool:
        fact = await self.get(user_id, memory_id)
        if fact is None:
            return False
        self._replace(memory_id, embedding=tuple(vector), embedding_model=model)
        return True

    async def mark_accessed(self, user_id: str, memory_ids: list[str]) -> None:
        now = datetime.now(timezone.utc)
        wanted = set(memory_ids)
        for fact in list(self._facts):
            if fact.user_id == user_id and fact.id in wanted:
                self._replace(
                    fact.id,
                    last_accessed_at=now,
                    access_count=fact.access_count + 1,
                )

    async def list_unembedded(self, limit: int = 50) -> list[tuple[str, str]]:
        rows = [
            (fact.id, fact.user_id)
            for fact in self._facts
            if fact.embedding is None and _is_active(fact)
        ]
        return rows[:limit]

    def _replace(self, memory_id: str, **changes) -> None:
        for index, fact in enumerate(self._facts):
            if fact.id == memory_id:
                self._facts[index] = replace(fact, **changes)
                return
