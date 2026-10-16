from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True)
class Attachment:
    kind: str
    file_id: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True)
class CallbackAction:
    data: str
    callback_id: str
    message_id: int | None = None


@dataclass(frozen=True)
class Button:
    text: str
    callback_data: str


@dataclass
class InboundMessage:
    channel: str
    external_user_id: str
    text: str | None
    attachments: list[Attachment] = field(default_factory=list)
    callback: CallbackAction | None = None
    received_at: datetime | None = None
    raw_id: str = ""
    username: str | None = None
    message_id: int | None = None


@dataclass
class OutboundMessage:
    text: str
    buttons: list[list[Button]] | None = None
    format: Literal["plain", "rich"] = "rich"
    reply_to: str | None = None


@dataclass(frozen=True)
class ChannelCapabilities:
    max_len: int
    supports_buttons: bool
    supports_edit: bool
    supports_markdown: bool


@dataclass
class UserChannel:
    id: str
    user_id: str
    channel: str
    external_id: str
    external_username: str | None
    status: str
    linked_at: datetime | None = None


@dataclass
class SendResult:
    ok: bool
    blocked: bool = False
    retry_after: float | None = None
    error: str | None = None
    message_id: int | None = None


class ChannelAdapter(Protocol):
    name: str
    capabilities: ChannelCapabilities

    async def send(self, user_channel: UserChannel | None, msg: OutboundMessage) -> SendResult: ...
