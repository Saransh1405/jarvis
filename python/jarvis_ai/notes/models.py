"""Note records."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Note:
    id: str
    user_id: str
    content: str
    created_at: datetime
