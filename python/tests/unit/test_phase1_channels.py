from datetime import datetime, timedelta, timezone

import pytest

from jarvis_ai.channels.base import Button, OutboundMessage, SendResult
from jarvis_ai.channels.linking import apply_link
from jarvis_ai.channels.memory import InMemoryChannelStore
from jarvis_ai.channels.parse import parse_callback, parse_command
from jarvis_ai.channels.render import render_telegram_html, split_telegram_messages
from jarvis_ai.channels.service import TelegramService
from jarvis_ai.conversations.memory import InMemoryConversationsStore
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.reminders.memory import InMemoryRemindersStore
from jarvis_ai.user_settings.memory import InMemoryUserSettingsStore


class RecordingTelegram:
    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []
        self.edits: list[str] = []
        self.answers: list[str | None] = []
        self.blocked = False

    async def send(self, user_channel, msg: OutboundMessage) -> SendResult:
        if self.blocked:
            return SendResult(ok=False, blocked=True, error="Forbidden: bot was blocked by the user")
        self.sent.append(msg)
        return SendResult(ok=True, message_id=len(self.sent))

    async def edit_message(self, chat_id: str, message_id: int, text: str, *, rich: bool = True) -> SendResult:
        self.edits.append(text)
        return SendResult(ok=True)

    async def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        self.answers.append(text)

    async def send_typing(self, chat_id: str) -> None:
        return None


class FakeOrchestrator:
    def __init__(self, reply: dict | None = None, approve: dict | None = None) -> None:
        self.chats: list[dict] = []
        self.approvals: list[tuple[str, str]] = []
        self.reply = reply or {"message": "42", "pending_action": None}
        self.approve = approve or {"message": "Reminder set.", "status": "executed"}

    async def chat(self, message, conversation_id=None, user_id=None, channel=None):
        self.chats.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "channel": channel,
            }
        )
        return self.reply

    async def approve_action(self, action_id: str, user_id: str | None):
        self.approvals.append((action_id, user_id or ""))
        return self.approve

    async def reject_action(self, action_id: str, user_id: str | None):
        self.approvals.append((action_id, user_id or ""))
        return {"message": "Cancelled `set_reminder`.", "status": "rejected"}


def _service(orch: FakeOrchestrator | None = None, clock=None) -> tuple[TelegramService, RecordingTelegram, InMemoryChannelStore]:
    telegram = RecordingTelegram()
    channels = InMemoryChannelStore()
    channels.labels["user-1"] = "sam"
    svc = TelegramService(
        channels=channels,
        conversations=InMemoryConversationsStore(),
        orchestrator=orch or FakeOrchestrator(),
        telegram=telegram,
        settings_store=InMemoryUserSettingsStore(),
        notes=InMemoryNotesStore(),
        reminders=InMemoryRemindersStore(),
        bot_username="@jarvis_bot",
        clock=clock,
    )
    return svc, telegram, channels


def test_render_escapes_html_and_keeps_bold() -> None:
    rendered = render_telegram_html("a < b and **bold** and `x<y`")
    assert "a &lt; b" in rendered
    assert "<b>bold</b>" in rendered
    assert "<code>x&lt;y</code>" in rendered
    assert "<script>" not in rendered


def test_split_prefers_paragraphs() -> None:
    text = "intro\n\n" + ("word " * 2000)
    parts = split_telegram_messages(text, limit=500)
    assert len(parts) > 1
    assert all(len(part) <= 500 for part in parts)
    assert parts[0].startswith("intro")


def test_parse_callback_rejects_non_uuid() -> None:
    assert parse_callback("a:not-a-uuid") is None
    action_id = "11111111-1111-1111-1111-111111111111"
    assert parse_callback(f"a:{action_id}") == ("a", action_id)
    assert len(f"a:{action_id}") <= 64
    assert parse_command("/timezone@jarvis_bot Asia/Kolkata") == ("/timezone", "Asia/Kolkata")


def test_link_rules_block_a_chat_owned_by_someone_else() -> None:
    from jarvis_ai.channels.base import UserChannel

    existing = UserChannel(
        id="1",
        user_id="user-a",
        channel="telegram",
        external_id="42",
        external_username="a",
        status="active",
    )
    _, code = apply_link(
        [existing],
        user_id="user-b",
        channel="telegram",
        external_id="42",
        username="b",
        now=datetime.now(timezone.utc),
    )
    assert code == "linked_to_other"


@pytest.mark.asyncio
async def test_link_token_is_single_use_and_expires() -> None:
    current = {"now": datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)}
    svc, telegram, _channels = _service(clock=lambda: current["now"])
    started = await svc.start_link("user-1")
    token = started["url"].split("start=", 1)[1]
    assert started["url"].startswith("https://t.me/jarvis_bot?start=")

    await svc.handle_update(_start_update(1, token))
    assert (await svc.status("user-1"))["linked"] is True
    assert "sam" in telegram.sent[-1].text

    await svc.handle_update(_start_update(2, token))
    assert "expired" in telegram.sent[-1].text or "already used" in telegram.sent[-1].text

    fresh = await svc.start_link("user-1")
    late = fresh["url"].split("start=", 1)[1]
    current["now"] = current["now"] + timedelta(minutes=11)
    await svc.handle_update(_start_update(3, late, chat_id=99))
    assert "expired" in telegram.sent[-1].text


@pytest.mark.asyncio
async def test_unlinked_chat_never_reaches_the_agent() -> None:
    orch = FakeOrchestrator()
    svc, telegram, _channels = _service(orch)
    for update_id in range(6):
        await svc.handle_update(
            {"update_id": update_id + 1, "message": {"text": "hello", "chat": {"id": 7}}}
        )
    assert orch.chats == []
    assert len(telegram.sent) == 5


@pytest.mark.asyncio
async def test_duplicate_update_does_not_double_reply() -> None:
    orch = FakeOrchestrator()
    svc, telegram, channels = _service(orch)
    await channels.link("user-1", "telegram", "7", "sam", datetime.now(timezone.utc))
    update = {"update_id": 10, "message": {"text": "calc 2+2", "chat": {"id": 7}}}
    await svc.handle_update(update)
    await svc.handle_update(update)
    assert len(orch.chats) == 1
    assert orch.chats[0]["channel"] == "telegram"
    assert len(telegram.sent) == 1


@pytest.mark.asyncio
async def test_pending_action_renders_approve_and_reject() -> None:
    action_id = "11111111-1111-1111-1111-111111111111"
    orch = FakeOrchestrator(
        reply={
            "message": "Set a reminder?",
            "pending_action": {"action_id": action_id, "tool_name": "set_reminder", "arguments": {}},
        }
    )
    svc, telegram, channels = _service(orch)
    await channels.link("user-1", "telegram", "7", None, datetime.now(timezone.utc))
    await svc.handle_update({"update_id": 1, "message": {"text": "remind me", "chat": {"id": 7}}})
    buttons = telegram.sent[-1].buttons or []
    flat = [button for row in buttons for button in row]
    assert flat == [
        Button(text="✅ Approve", callback_data=f"a:{action_id}"),
        Button(text="❌ Reject", callback_data=f"r:{action_id}"),
    ]


@pytest.mark.asyncio
async def test_foreign_approve_button_does_nothing() -> None:
    action_id = "22222222-2222-2222-2222-222222222222"
    orch = FakeOrchestrator(approve={"error": "action not found", "status_code": 404})
    svc, telegram, channels = _service(orch)
    await channels.link("user-1", "telegram", "7", None, datetime.now(timezone.utc))
    await svc.handle_update(
        {
            "update_id": 4,
            "callback_query": {
                "id": "cb",
                "data": f"a:{action_id}",
                "message": {"message_id": 3, "chat": {"id": 7}},
            },
        }
    )
    assert orch.approvals == [(action_id, "user-1")]
    assert telegram.edits[-1] == "That action is not yours."


@pytest.mark.asyncio
async def test_blocked_bot_marks_the_channel() -> None:
    svc, telegram, channels = _service()
    await channels.link("user-1", "telegram", "7", None, datetime.now(timezone.utc))
    telegram.blocked = True
    await svc.handle_update({"update_id": 1, "message": {"text": "hi", "chat": {"id": 7}}})
    row = await channels.get_for_user("user-1", "telegram")
    assert row is not None
    assert row.status == "blocked"


def _start_update(update_id: int, token: str, chat_id: int = 42) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "text": f"/start {token}",
            "chat": {"id": chat_id},
            "from": {"username": "sam"},
        },
    }
