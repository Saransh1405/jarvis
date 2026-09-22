from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PendingActionRecord:
    id: str
    user_id: str
    conversation_id: str | None
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    messages: list[dict[str, Any]]
    status: str
    created_at: datetime
