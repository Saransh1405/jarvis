from datetime import datetime, timedelta, timezone

import pytest

from jarvis_ai.memory.extraction import extract_chat_facts
from jarvis_ai.memory.helpers import add_fact_if_new, store_extracted_facts
from jarvis_ai.memory.store import InMemoryMemoryStore, MemoryFact
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.tools import build_default_registry
from jarvis_ai.tools.context import ToolContext
from jarvis_ai.llm.stub import StubLLMProvider


@pytest.mark.asyncio
async def test_add_fact_if_new_dedupes_similar_content() -> None:
    store = InMemoryMemoryStore()
    first = await add_fact_if_new(store, "user-1", "gate code is 1234")
    second = await add_fact_if_new(store, "user-1", "gate code is 1234")
    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_memory_search_isolated_by_user() -> None:
    store = InMemoryMemoryStore()
    await store.add_fact("user-a", "plumber Raj 555-0100", source="chat")
    hits = await store.search("user-b", "plumber", limit=5)
    assert hits == []


@pytest.mark.asyncio
async def test_search_empty_query_returns_recent() -> None:
    store = InMemoryMemoryStore()
    await store.add_fact("user-1", "older", source="chat")
    await store.add_fact("user-1", "newer", source="chat")
    recent = await store.search("user-1", "", limit=1)
    assert len(recent) == 1
    assert recent[0].content == "newer"


@pytest.mark.asyncio
async def test_old_fact_still_searchable() -> None:
    store = InMemoryMemoryStore()
    old_time = datetime.now(timezone.utc) - timedelta(days=8)
    store._facts.append(
        MemoryFact(
            id="old-1",
            user_id="user-1",
            content="My plumber is Raj, number 555-0100",
            source="chat",
            created_at=old_time,
        )
    )
    hits = await store.search("user-1", "plumber", limit=5)
    assert any("Raj" in f.content for f in hits)


def test_extract_chat_facts_remember_prefix() -> None:
    facts = extract_chat_facts("Remember: passport renews in March")
    assert facts == ["passport renews in March"]


def test_extract_chat_facts_my_contact_statement() -> None:
    msg = "My plumber is Raj, number 555-0100"
    facts = extract_chat_facts(msg)
    assert msg in facts


@pytest.mark.asyncio
async def test_orchestrator_extracts_memory_after_chat_turn() -> None:
    memory = InMemoryMemoryStore()
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=build_default_registry(),
        memory=memory,
    )
    await orch.chat("My plumber is Raj, number 555-0100", None, user_id="user-1")
    hits = await memory.search("user-1", "plumber", limit=5)
    assert any("Raj" in f.content for f in hits)


@pytest.mark.asyncio
async def test_remember_fact_tool_stores_for_recall_in_new_conversation() -> None:
    registry = build_default_registry()
    memory = InMemoryMemoryStore()
    ctx = ToolContext(user_id="user-1", memory=memory)
    await registry.run(
        "remember_fact",
        {"content": "My plumber is Raj, number 555-0100"},
        ctx,
    )
    orch = Orchestrator(
        llm=StubLLMProvider(),
        tools=registry,
        memory=memory,
    )
    prompt = await orch._build_system_prompt("user-1", "What did I tell you about the plumber?")
    assert "Raj" in prompt or "555-0100" in prompt


@pytest.mark.asyncio
async def test_store_extracted_facts_respects_max_per_turn() -> None:
    store = InMemoryMemoryStore()
    count = await store_extracted_facts(
        store,
        "user-1",
        ["fact one", "fact two", "fact three", "fact four"],
    )
    assert count == 3
    assert len(await store.recent("user-1", limit=10)) == 3
