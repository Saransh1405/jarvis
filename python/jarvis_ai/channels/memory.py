"""In-memory channel store for tests and local runs without Postgres."""

from datetime import datetime, timezone
from uuid import uuid4

from jarvis_ai.channels.base import UserChannel
from jarvis_ai.channels.linking import apply_link


class InMemoryChannelStore:
    def __init__(self) -> None:
        self.channels: list[UserChannel] = []
        self.tokens: dict[bytes, dict] = {}
        self.seen: set[tuple[str, int]] = set()
        self.labels: dict[str, str] = {}

    async def create_link_token(
        self, user_id: str, channel: str, token_hash: bytes, expires_at: datetime
    ) -> None:
        self.tokens[token_hash] = {
            "user_id": user_id,
            "channel": channel,
            "expires_at": expires_at,
            "used_at": None,
        }

    async def consume_link_token(self, token_hash: bytes, channel: str, now: datetime) -> str | None:
        row = self.tokens.get(token_hash)
        if row is None or row["channel"] != channel or row["used_at"] is not None:
            return None
        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return None
        row["used_at"] = now
        return str(row["user_id"])

    async def get_by_external(self, channel: str, external_id: str) -> UserChannel | None:
        for row in self.channels:
            if row.channel == channel and row.external_id == external_id:
                return row
        return None

    async def get_for_user(self, user_id: str, channel: str) -> UserChannel | None:
        for row in self.channels:
            if row.user_id == user_id and row.channel == channel:
                return row
        return None

    async def link(
        self,
        user_id: str,
        channel: str,
        external_id: str,
        username: str | None,
        now: datetime | None = None,
    ) -> str:
        moment = now or datetime.now(timezone.utc)
        relevant = [
            row
            for row in self.channels
            if (row.channel == channel and row.external_id == external_id)
            or (row.user_id == user_id and row.channel == channel)
        ]
        updated, code = apply_link(
            relevant,
            user_id=user_id,
            channel=channel,
            external_id=external_id,
            username=username,
            now=moment,
            new_id=str(uuid4()),
        )
        if code != "ok":
            return code
        drop = {row.id for row in relevant}
        self.channels = [row for row in self.channels if row.id not in drop]
        self.channels.extend(updated)
        return "ok"

    async def set_status(self, user_id: str, channel: str, status: str) -> bool:
        for index, row in enumerate(self.channels):
            if row.user_id == user_id and row.channel == channel:
                self.channels[index] = UserChannel(
                    id=row.id,
                    user_id=row.user_id,
                    channel=row.channel,
                    external_id=row.external_id,
                    external_username=row.external_username,
                    status=status,
                    linked_at=row.linked_at,
                )
                return True
        return False

    async def touch_inbound(self, channel: str, external_id: str) -> None:
        return None

    async def mark_update_seen(self, channel: str, update_id: int) -> bool:
        key = (channel, update_id)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True

    async def user_label(self, user_id: str) -> str:
        return self.labels.get(user_id, "your account")
