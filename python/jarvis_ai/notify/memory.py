from datetime import datetime, timezone
from uuid import uuid4


class InMemoryNotificationLog:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def insert(
        self,
        *,
        user_id: str,
        kind: str,
        channel: str,
        status: str,
        dedupe_key: str | None = None,
        ref_id: str | None = None,
        error: str | None = None,
    ) -> str | None:
        if dedupe_key and status in ("queued", "sent"):
            for row in self.rows:
                if row["dedupe_key"] == dedupe_key and row["status"] in ("queued", "sent"):
                    return None
        row_id = str(uuid4())
        self.rows.append(
            {
                "id": row_id,
                "user_id": user_id,
                "kind": kind,
                "channel": channel,
                "status": status,
                "dedupe_key": dedupe_key,
                "ref_id": ref_id,
                "error": error,
                "sent_at": datetime.now(timezone.utc) if status == "sent" else None,
            }
        )
        return row_id

    async def mark(self, notification_id: str, status: str, error: str | None = None) -> None:
        for row in self.rows:
            if row["id"] == notification_id:
                row["status"] = status
                row["error"] = error
                if status == "sent":
                    row["sent_at"] = datetime.now(timezone.utc)
                return
