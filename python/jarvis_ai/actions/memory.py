"""In-memory pending actions for tests."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from jarvis_ai.actions.models import PendingActionRecord


class InMemoryPendingActionsStore:
    def __init__(self) -> None:
        self._items: dict[str, PendingActionRecord] = {}

    async def create(
        self,
        user_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        messages: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> str:
        action_id = str(uuid4())
        self._items[action_id] = PendingActionRecord(
            id=action_id,
            user_id=user_id,
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=arguments,
            messages=messages,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        return action_id

    async def get_for_user(self, action_id: str, user_id: str) -> PendingActionRecord | None:
        record = self._items.get(action_id)
        if record is None or record.user_id != user_id:
            return None
        return record

    async def set_status(self, action_id: str, user_id: str, status: str) -> bool:
        record = self._items.get(action_id)
        if record is None or record.user_id != user_id or record.status != "pending":
            return False
        self._items[action_id] = PendingActionRecord(
            id=record.id,
            user_id=record.user_id,
            conversation_id=record.conversation_id,
            tool_call_id=record.tool_call_id,
            tool_name=record.tool_name,
            arguments=record.arguments,
            messages=record.messages,
            status=status,
            created_at=record.created_at,
        )
        return True
