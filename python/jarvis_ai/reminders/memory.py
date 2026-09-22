from datetime import datetime, timezone
from uuid import uuid4

from jarvis_ai.reminders.models import Reminder


class InMemoryRemindersStore:
    def __init__(self) -> None:
        self._items: list[Reminder] = []

    async def create(self, user_id: str, message: str, due_at: datetime) -> str:
        reminder_id = str(uuid4())
        self._items.append(
            Reminder(
                id=reminder_id,
                user_id=user_id,
                message=message,
                due_at=due_at,
                done=False,
            )
        )
        return reminder_id

    async def list_for_user(self, user_id: str, include_done: bool = False) -> list[Reminder]:
        items = [r for r in self._items if r.user_id == user_id]
        if not include_done:
            items = [r for r in items if not r.done]
        return sorted(items, key=lambda r: r.due_at)

    async def list_due(self, user_id: str, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now(timezone.utc)
        return [
            r
            for r in self._items
            if r.user_id == user_id and not r.done and r.due_at <= now
        ]

    async def mark_done(self, user_id: str, reminder_id: str) -> bool:
        for idx, reminder in enumerate(self._items):
            if reminder.id == reminder_id and reminder.user_id == user_id:
                self._items[idx] = Reminder(
                    id=reminder.id,
                    user_id=reminder.user_id,
                    message=reminder.message,
                    due_at=reminder.due_at,
                    done=True,
                )
                return True
        return False
