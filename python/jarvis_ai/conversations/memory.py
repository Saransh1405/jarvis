"""In-memory conversations store for tests."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from jarvis_ai.conversations.models import Conversation, Message


class InMemoryConversationsStore:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[Message]] = {}

    async def create_conversation(self, user_id: str) -> str:
        conv_id = str(uuid4())
        now = datetime.now(timezone.utc)
        self._conversations[conv_id] = Conversation(
            id=conv_id,
            user_id=user_id,
            title=None,
            created_at=now,
            updated_at=now,
        )
        self._messages[conv_id] = []
        return conv_id

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        conv = self._conversations.get(conversation_id)
        if conv is None or conv.user_id != user_id:
            return None
        return conv

    async def touch_conversation(self, conversation_id: str) -> None:
        conv = self._conversations.get(conversation_id)
        if conv is None:
            return
        self._conversations[conversation_id] = Conversation(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=datetime.now(timezone.utc),
        )

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        conv = await self.get_conversation(user_id, conversation_id)
        if conv is None:
            raise ValueError("conversation not found")
        msg = Message(
            id=str(uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            metadata=dict(metadata or {}),
            created_at=datetime.now(timezone.utc),
        )
        self._messages.setdefault(conversation_id, []).append(msg)
        await self.touch_conversation(conversation_id)

    async def list_messages(
        self, user_id: str, conversation_id: str, limit: int = 100
    ) -> list[Message]:
        conv = await self.get_conversation(user_id, conversation_id)
        if conv is None:
            return []
        msgs = self._messages.get(conversation_id, [])
        if len(msgs) <= limit:
            return list(msgs)
        return list(msgs[-limit:])

    async def list_conversations(self, user_id: str, limit: int = 20) -> list[Conversation]:
        convs = [c for c in self._conversations.values() if c.user_id == user_id]
        convs.sort(key=lambda c: c.updated_at, reverse=True)
        return convs[:limit]
