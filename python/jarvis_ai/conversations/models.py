from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Conversation:
    id: str
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    user_id: str
    role: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime
