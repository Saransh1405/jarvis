from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from jarvis_ai.reminders.models import Reminder

_TERMINAL = ("done", "cancelled")


class InMemoryRemindersStore:
    def __init__(self) -> None:
        self._items: list[Reminder] = []

    async def create(
        self,
        user_id: str,
        message: str,
        due_at: datetime,
        *,
        timezone: str = "UTC",
        rrule: str | None = None,
        source: str = "chat",
        lead_minutes: int | None = None,
        status: str = "scheduled",
    ) -> str:
        reminder_id = str(uuid4())
        self._items.append(
            Reminder(
                id=reminder_id,
                user_id=user_id,
                message=message,
                due_at=due_at,
                done=status in _TERMINAL,
                timezone=timezone,
                status=status,
                rrule=rrule,
                lead_minutes=lead_minutes,
                source=source,
            )
        )
        return reminder_id

    async def get(self, reminder_id: str) -> Reminder | None:
        for reminder in self._items:
            if reminder.id == reminder_id:
                return reminder
        return None

    async def get_for_user(self, user_id: str, reminder_id: str) -> Reminder | None:
        reminder = await self.get(reminder_id)
        if reminder is None or reminder.user_id != user_id:
            return None
        return reminder

    async def list_for_user(self, user_id: str, include_done: bool = False) -> list[Reminder]:
        items = [r for r in self._items if r.user_id == user_id]
        if not include_done:
            items = [r for r in items if not r.done]
        return sorted(items, key=lambda r: r.due_at)

    async def list_due(self, user_id: str, now: datetime | None = None) -> list[Reminder]:
        moment = now or datetime.now(timezone.utc)
        return [
            r
            for r in self._items
            if r.user_id == user_id and not r.done and r.due_at <= moment
        ]

    async def list_between(
        self,
        user_id: str,
        start: datetime,
        end: datetime,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Reminder]:
        items = []
        for reminder in self._items:
            if reminder.user_id != user_id:
                continue
            if reminder.due_at < start or reminder.due_at >= end:
                continue
            if statuses is not None and reminder.status not in statuses:
                continue
            if statuses is None and reminder.status in _TERMINAL:
                continue
            items.append(reminder)
        return sorted(items, key=lambda r: r.due_at)

    async def apply_delivery(
        self,
        reminder_id: str,
        *,
        status: str,
        due_at: datetime | None = None,
        last_fired_at: datetime | None = None,
        done: bool | None = None,
    ) -> bool:
        for idx, reminder in enumerate(self._items):
            if reminder.id != reminder_id:
                continue
            done_flag = status in _TERMINAL if done is None else done
            self._items[idx] = replace(
                reminder,
                status=status,
                done=done_flag,
                due_at=due_at or reminder.due_at,
                last_fired_at=last_fired_at or reminder.last_fired_at,
            )
            return True
        return False

    async def mark_done(self, user_id: str, reminder_id: str) -> bool:
        reminder = await self.get_for_user(user_id, reminder_id)
        if reminder is None:
            return False
        return await self.apply_delivery(reminder_id, status="done", done=True)
