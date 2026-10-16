from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reminder:
    id: str
    user_id: str
    message: str
    due_at: datetime
    done: bool
    timezone: str = "UTC"
    status: str = "scheduled"
    last_fired_at: datetime | None = None
    rrule: str | None = None
    lead_minutes: int | None = None
    source: str = "chat"
