import os

import pytest

from jarvis_ai.db import create_pool, run_migrations
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.notes.repository import NotesRepository


@pytest.mark.asyncio
async def test_in_memory_notes_round_trip() -> None:
    store = InMemoryNotesStore()
    note_id = await store.create("u1", "hello world")
    note = await store.get_for_user("u1", note_id)
    assert note is not None
    assert note.content == "hello world"
    recent = await store.list_recent("u1")
    assert len(recent) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_notes_round_trip() -> None:
    dsn = os.environ.get("JARVIS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set")

    pool = await create_pool(dsn)
    try:
        await run_migrations(pool)
        repo = NotesRepository(pool)
        user_id = "integration-test-user"
        note_id = await repo.create(user_id, "persisted note")
        fetched = await repo.get_for_user(user_id, note_id)
        assert fetched is not None
        assert fetched.content == "persisted note"
    finally:
        await pool.close()
