"""Per-request context passed into tool handlers."""

from dataclasses import dataclass
from typing import Any, Protocol


class NotesStore(Protocol):
    async def create(self, user_id: str, content: str) -> str: ...

    async def get_for_user(self, user_id: str, note_id: str) -> Any | None: ...

    async def list_recent(self, user_id: str, limit: int = 10) -> list[Any]: ...


class RemindersStore(Protocol):
    async def create(self, user_id: str, message: str, due_at: Any) -> str: ...

    async def list_for_user(self, user_id: str, include_done: bool = False) -> list[Any]: ...

    async def list_due(self, user_id: str, now: Any | None = None) -> list[Any]: ...


class MemoryStore(Protocol):
    async def add_fact(self, user_id: str, content: str, source: str = "chat") -> str: ...

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[Any]: ...


class PendingActionsStore(Protocol):
    async def create(
        self,
        user_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        messages: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> str: ...

    async def get_for_user(self, action_id: str, user_id: str) -> Any | None: ...

    async def set_status(self, action_id: str, user_id: str, status: str) -> bool: ...


class ToolCallLogStore(Protocol):
    async def log(
        self,
        user_id: str | None,
        tool_name: str,
        arguments: dict[str, Any],
        result: str,
    ) -> None: ...


@dataclass
class ToolContext:
    """Identity and services available during tool execution."""

    user_id: str | None = None
    notes: NotesStore | None = None
    reminders: RemindersStore | None = None
    memory: MemoryStore | None = None
