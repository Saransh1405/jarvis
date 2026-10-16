from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScheduledJob:
    id: str
    kind: str
    user_id: str
    run_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "scheduled"
    attempts: int = 0
    max_attempts: int = 5
    locked_until: datetime | None = None
    last_error: str | None = None
    dedupe_key: str | None = None


def backoff_seconds(attempts: int) -> int:
    """30s, 2m, 10m, then 1h. `attempts` is the count after a failed claim."""
    schedule = (30, 120, 600, 3600)
    index = max(attempts - 1, 0)
    if index >= len(schedule):
        return schedule[-1]
    return schedule[index]
