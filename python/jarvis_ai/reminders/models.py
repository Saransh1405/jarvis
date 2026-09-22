from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reminder:
    id: str
    user_id: str
    message: str
    due_at: datetime
    done: bool
