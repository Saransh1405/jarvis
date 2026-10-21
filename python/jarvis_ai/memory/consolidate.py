"""Decide whether a candidate memory is new, a duplicate, or a contradiction."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from jarvis_ai.memory.filters import is_secret

SIMILAR_THRESHOLD = 0.85
DUPLICATE_THRESHOLD = 0.92

Judge = Callable[[str, str], Awaitable[str]]


@dataclass(frozen=True)
class Candidate:
    content: str
    kind: str = "fact"
    importance: int = 3
    confidence: float = 0.8


@dataclass(frozen=True)
class ConsolidateResult:
    action: str
    memory_id: str | None = None
    content: str = ""


def heuristic_judge(new: str, old: str) -> str:
    left = " ".join(new.lower().split())
    right = " ".join(old.lower().split())
    if left == right or left in right or right in left:
        return "duplicate"
    left_place = _place(left)
    right_place = _place(right)
    if left_place and right_place and left_place != right_place:
        return "contradiction"
    left_job = _role(left)
    right_job = _role(right)
    if left_job and right_job and left_job != right_job:
        return "contradiction"
    return "new"


def _place(text: str) -> str:
    for marker in ("moved to ", "lives in ", "live in ", "living in "):
        if marker in text:
            return text.split(marker, 1)[1].split(".")[0].strip()
    return ""


def _role(text: str) -> str:
    for marker in ("works at ", "worked at ", "job is ", "job was "):
        if marker in text:
            return text.split(marker, 1)[1].split(".")[0].strip()
    return ""


async def llm_judge(llm, new: str, old: str) -> str:
    if llm is None or getattr(llm, "name", "") == "stub":
        return heuristic_judge(new, old)
    raw = await llm.complete(
        f"Existing memory: {old}\nNew memory: {new}\n"
        "Reply with exactly one word: duplicate, contradiction, or new.",
        system="You compare two memories about the same person. Reply with one word.",
    )
    word = (raw or "").strip().lower()
    if "contradict" in word:
        return "contradiction"
    if "duplicate" in word:
        return "duplicate"
    return "new"


async def consolidate(
    store,
    user_id: str,
    candidate: Candidate,
    judge: Judge,
    *,
    source: str = "extracted",
    allow_sensitive: bool = False,
    sensitive_ok: bool = True,
) -> ConsolidateResult:
    del allow_sensitive
    if is_secret(candidate.content) or not sensitive_ok:
        return ConsolidateResult("rejected", content=candidate.content)

    vector = None
    embedder = getattr(store, "embedder", None)
    if embedder is not None:
        vector = list(await embedder.embed(candidate.content))
    similar = []
    if vector is not None:
        similar = await store.search_semantic(user_id, vector, limit=5)
    close = [fact for fact in similar if fact.similarity >= SIMILAR_THRESHOLD]
    close.sort(key=lambda fact: fact.similarity, reverse=True)

    if close:
        top = close[0]
        decision = "duplicate" if top.similarity >= DUPLICATE_THRESHOLD else await judge(
            candidate.content, top.content
        )
        if decision == "duplicate":
            await store.touch(user_id, top.id)
            return ConsolidateResult("duplicate", top.id, top.content)
        if decision == "contradiction":
            new_id, _embedded = await store.add(
                user_id,
                candidate.content,
                source=source,
                kind=candidate.kind,
                importance=candidate.importance,
                confidence=candidate.confidence,
                embedding=vector,
                embedding_model=getattr(embedder, "model", None),
                embed=False,
            )
            await store.supersede(user_id, top.id, new_id)
            return ConsolidateResult("superseded", new_id, candidate.content)

    new_id, _embedded = await store.add(
        user_id,
        candidate.content,
        source=source,
        kind=candidate.kind,
        importance=candidate.importance,
        confidence=candidate.confidence,
        embedding=vector,
        embedding_model=getattr(embedder, "model", None),
        embed=vector is None,
    )
    return ConsolidateResult("new", new_id, candidate.content)
