import pytest

from jarvis_ai.conversations.memory import InMemoryConversationsStore


@pytest.mark.asyncio
async def test_create_and_list_messages() -> None:
    store = InMemoryConversationsStore()
    conv_id = await store.create_conversation("user-a")
    await store.append_message("user-a", conv_id, "user", "hello")
    await store.append_message("user-a", conv_id, "assistant", "hi there")

    msgs = await store.list_messages("user-a", conv_id)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].content == "hi there"


@pytest.mark.asyncio
async def test_user_b_cannot_access_user_a_conversation() -> None:
    store = InMemoryConversationsStore()
    conv_id = await store.create_conversation("user-a")
    assert await store.get_conversation("user-b", conv_id) is None
    assert await store.list_messages("user-b", conv_id) == []


@pytest.mark.asyncio
async def test_list_conversations_scoped_by_user() -> None:
    store = InMemoryConversationsStore()
    await store.create_conversation("user-a")
    await store.create_conversation("user-b")
    a_convs = await store.list_conversations("user-a")
    assert len(a_convs) == 1
    assert a_convs[0].user_id == "user-a"
