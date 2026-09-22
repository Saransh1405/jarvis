"""In-memory notes store for tests and local dev without Postgres."""

from datetime import datetime, timezone
from uuid import uuid4

from jarvis_ai.notes.models import Note


class InMemoryNotesStore:
    """Simple per-user note list (not durable)."""

    def __init__(self) -> None:
        self._by_user: dict[str, list[Note]] = {}

    async def create(self, user_id: str, content: str) -> str:
        note_id = str(uuid4())
        note = Note(
            id=note_id,
            user_id=user_id,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        self._by_user.setdefault(user_id, []).insert(0, note)
        return note_id

    async def get_for_user(self, user_id: str, note_id: str) -> Note | None:
        for note in self._by_user.get(user_id, []):
            if note.id == note_id:
                return note
        return None

    async def list_recent(self, user_id: str, limit: int = 10) -> list[Note]:
        return list(self._by_user.get(user_id, [])[:limit])
