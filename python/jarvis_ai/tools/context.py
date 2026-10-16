"""Per-request context passed into tool handlers."""

from dataclasses import dataclass
from typing import Any, Protocol


class NotesStore(Protocol):
    async def create(self, user_id: str, content: str) -> str: ...

    async def get_for_user(self, user_id: str, note_id: str) -> Any | None: ...

    async def list_recent(self, user_id: str, limit: int = 10) -> list[Any]: ...


class RemindersStore(Protocol):
    async def create(
        self,
        user_id: str,
        message: str,
        due_at: Any,
        *,
        timezone: str = "UTC",
        rrule: str | None = None,
        source: str = "chat",
        lead_minutes: int | None = None,
        status: str = "scheduled",
    ) -> str: ...

    async def list_for_user(self, user_id: str, include_done: bool = False) -> list[Any]: ...

    async def list_due(self, user_id: str, now: Any | None = None) -> list[Any]: ...

    async def get_for_user(self, user_id: str, reminder_id: str) -> Any | None: ...

    async def apply_delivery(self, reminder_id: str, *, status: str, due_at: Any = None, last_fired_at: Any = None, done: bool | None = None) -> bool: ...


class JobQueue(Protocol):
    async def enqueue(
        self,
        *,
        kind: str,
        user_id: str,
        run_at: Any,
        payload: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        max_attempts: int = 5,
    ) -> Any: ...

    async def cancel_by_dedupe(self, dedupe_key: str) -> None: ...


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

    async def set_status(
        self, action_id: str, user_id: str, status: str, *, only_if: str | None = "pending"
    ) -> bool: ...


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
    timezone: str = "UTC"
    notes: NotesStore | None = None
    reminders: RemindersStore | None = None
    memory: MemoryStore | None = None
    jobs: JobQueue | None = None
