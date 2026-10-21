"""Telegram inbound handling: link, commands, chat, and approve/reject."""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jarvis_ai.channels.base import Button, OutboundMessage, UserChannel
from jarvis_ai.channels.limits import SlidingWindowLimiter
from jarvis_ai.channels.parse import hash_link_token, parse_callback, parse_command
from jarvis_ai.reminders.actions import complete_reminder, snooze_reminder
from jarvis_ai.user_settings.formatting import format_datetime_local
from jarvis_ai.user_settings.tz import canonical_timezone

logger = logging.getLogger(__name__)

LINK_TTL = timedelta(minutes=10)
UNLINKED_REPLY = (
    "This chat is not linked yet. Open JARVIS on the web, go to Settings, "
    "and tap Connect Telegram."
)
HELP_TEXT = (
    "I can chat, take notes, and set reminders.\n\n"
    "/new — start a fresh conversation\n"
    "/reminders — list upcoming reminders\n"
    "/brief — send today's brief now\n"
    "/memory — show what I remember\n"
    "/forget <text> — delete a matching memory\n"
    "/notes — recent notes\n"
    "/timezone Asia/Kolkata — set your timezone\n"
    "/settings — show current settings\n"
    "/unlink — disconnect this chat\n"
    "/help — this message"
)


class TelegramService:
    def __init__(
        self,
        *,
        channels,
        conversations,
        orchestrator,
        telegram,
        settings_store,
        notes,
        reminders,
        bot_username: str,
        feature_enabled: bool = True,
        clock=None,
        jobs=None,
        briefs=None,
        memory=None,
    ) -> None:
        self._channels = channels
        self._conversations = conversations
        self._orchestrator = orchestrator
        self._telegram = telegram
        self._settings = settings_store
        self._notes = notes
        self._reminders = reminders
        self._jobs = jobs
        self._briefs = briefs
        self._memory = memory
        self._bot_username = bot_username.lstrip("@")
        self._feature_enabled = feature_enabled
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()
        self._unlinked = SlidingWindowLimiter(limit=5, window_seconds=3600)

    def _now(self) -> datetime:
        return self._clock()

    async def start_link(self, user_id: str) -> dict:
        if not self._bot_username:
            raise RuntimeError("telegram bot username is not configured")
        token = secrets.token_urlsafe(32)
        expires_at = self._now() + LINK_TTL
        await self._channels.create_link_token(
            user_id, "telegram", hash_link_token(token), expires_at
        )
        return {
            "url": f"https://t.me/{self._bot_username}?start={token}",
            "expires_at": expires_at.isoformat(),
        }

    async def status(self, user_id: str) -> dict:
        row = await self._channels.get_for_user(user_id, "telegram")
        if row is None:
            return {"linked": False, "status": None, "username": None}
        return {
            "linked": row.status == "active",
            "status": row.status,
            "username": row.external_username,
        }

    async def unlink(self, user_id: str) -> dict:
        await self._channels.set_status(user_id, "telegram", "unlinked")
        await self._settings.set_preferred_channel(user_id, "web")
        return {"linked": False, "status": "unlinked", "username": None}

    async def handle_update(self, update: dict) -> None:
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            logger.info("telegram update missing update_id")
            return
        fresh = await self._channels.mark_update_seen("telegram", update_id)
        if not fresh:
            return

        message = update.get("message") or {}
        callback = update.get("callback_query") or {}
        if callback:
            chat = (callback.get("message") or {}).get("chat") or {}
        else:
            chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        external_id = str(chat_id)
        lock = await self._lock_for(external_id)
        async with lock:
            if callback:
                await self._handle_callback(callback, external_id)
                return
            await self._handle_message(message, external_id)

    async def _handle_message(self, message: dict, external_id: str) -> None:
        username = (message.get("from") or {}).get("username")
        text = message.get("text") if isinstance(message.get("text"), str) else ""
        if not self._feature_enabled:
            await self._reply(external_id, "Telegram is turned off right now.")
            return

        command = parse_command(text) if text.strip() else None
        if command and command[0] == "/start":
            await self._handle_start(external_id, username, command[1])
            return

        row = await self._channels.get_by_external("telegram", external_id)
        if row is None or row.status != "active":
            if self._unlinked.allow(external_id):
                await self._reply(external_id, UNLINKED_REPLY)
            return

        await self._channels.touch_inbound("telegram", external_id)
        if not text.strip():
            await self._reply(external_id, "I can only read text right now.")
            return
        if command:
            reply = await self._run_command(row, command[0], command[1])
            await self._send(row, reply)
            return

        await self._chat(row, text)

    async def _handle_start(self, external_id: str, username: str | None, arg: str) -> None:
        token = arg.strip()
        if not token:
            row = await self._channels.get_by_external("telegram", external_id)
            if row is not None and row.status == "active":
                await self._reply(external_id, "You're already linked. Say hello, or try /help.")
                return
            await self._reply(external_id, UNLINKED_REPLY)
            return

        user_id = await self._channels.consume_link_token(
            hash_link_token(token), "telegram", self._now()
        )
        if not user_id:
            await self._reply(
                external_id,
                "That link has expired or was already used. Generate a new one from JARVIS settings.",
            )
            return
        code = await self._channels.link(user_id, "telegram", external_id, username, self._now())
        if code != "ok":
            await self._reply(
                external_id,
                "This Telegram chat is already linked to another account. Send /unlink from that account first.",
            )
            return
        await self._settings.set_preferred_channel(user_id, "telegram")
        label = await self._channels.user_label(user_id)
        await self._reply(
            external_id,
            f"Linked to {label}. Try: remind me to call mom tomorrow at 6pm.",
        )

    async def _run_command(self, row: UserChannel, name: str, arg: str) -> OutboundMessage:
        if name == "/help":
            return OutboundMessage(text=HELP_TEXT, format="plain")
        if name == "/new":
            await self._conversations.create_conversation(
                row.user_id, channel="telegram", channel_chat_id=row.external_id
            )
            return OutboundMessage(text="Started a new conversation.", format="plain")
        if name == "/unlink":
            await self.unlink(row.user_id)
            return OutboundMessage(text="Telegram disconnected.", format="plain")
        if name == "/timezone":
            return await self._timezone(row.user_id, arg)
        if name == "/settings":
            return await self._settings_summary(row.user_id)
        if name == "/reminders":
            return await self._reminders_list(row.user_id)
        if name == "/notes":
            return await self._notes_list(row.user_id)
        if name == "/brief":
            return await self._brief(row.user_id)
        if name == "/memory":
            return await self._memory_page(row.user_id, arg)
        if name == "/forget":
            return await self._forget(row.user_id, arg)
        return OutboundMessage(text=HELP_TEXT, format="plain")

    async def _timezone(self, user_id: str, arg: str) -> OutboundMessage:
        raw = arg.strip()
        if not raw:
            return OutboundMessage(
                text="Send /timezone followed by an IANA name, for example /timezone Asia/Kolkata.",
                format="plain",
            )
        canonical = canonical_timezone(raw)
        try:
            ZoneInfo(canonical)
        except Exception:
            return OutboundMessage(
                text=f"I don't recognize the timezone {raw}. Try an IANA name like Asia/Kolkata.",
                format="plain",
            )
        await self._settings.update_timezone(user_id, canonical)
        return OutboundMessage(text=f"Timezone set to {canonical}.", format="plain")

    async def _settings_summary(self, user_id: str) -> OutboundMessage:
        cfg = await self._settings.get(user_id)
        quiet = "off"
        if cfg.quiet_hours_start and cfg.quiet_hours_end:
            quiet = f"{cfg.quiet_hours_start}–{cfg.quiet_hours_end}"
        text = (
            f"Timezone: {cfg.timezone}\n"
            f"Preferred channel: {cfg.preferred_channel}\n"
            f"Morning brief: {'on' if cfg.brief_enabled else 'off'} at {cfg.brief_time_local}\n"
            f"Quiet hours: {quiet}\n"
            f"Learn from chats: {'on' if cfg.feature_flags.get('learn_from_conversations', True) else 'off'}"
        )
        return OutboundMessage(text=text, format="plain")

    async def _reminders_list(self, user_id: str) -> OutboundMessage:
        if self._reminders is None:
            return OutboundMessage(text="No upcoming reminders.", format="plain")
        cfg = await self._settings.get(user_id)
        items = await self._reminders.list_for_user(user_id, include_done=False)
        if not items:
            return OutboundMessage(text="No upcoming reminders.", format="plain")
        lines = ["Upcoming reminders:"]
        for reminder in items[:10]:
            when = format_datetime_local(reminder.due_at, cfg.timezone)
            lines.append(f"• {reminder.message} — {when}")
        return OutboundMessage(text="\n".join(lines), format="plain")

    async def _notes_list(self, user_id: str) -> OutboundMessage:
        if self._notes is None:
            return OutboundMessage(text="No notes yet.", format="plain")
        notes = await self._notes.list_recent(user_id, limit=5)
        if not notes:
            return OutboundMessage(text="No notes yet.", format="plain")
        lines = ["Recent notes:"]
        for note in notes:
            lines.append(f"• {note.content}")
        return OutboundMessage(text="\n".join(lines), format="plain")

    async def _chat(self, row: UserChannel, text: str) -> None:
        if self._telegram is not None:
            await self._telegram.send_typing(row.external_id)
        conversation_id = await self._conversation_id(row)
        result = await self._orchestrator.chat(
            text, conversation_id, user_id=row.user_id, channel="telegram"
        )
        if result.get("status_code"):
            await self._send(row, OutboundMessage(text="Something went wrong. Try again.", format="plain"))
            return
        pending = result.get("pending_action") or {}
        action_id = pending.get("action_id")
        buttons = None
        if action_id:
            buttons = [[
                Button(text="✅ Approve", callback_data=f"a:{action_id}"),
                Button(text="❌ Reject", callback_data=f"r:{action_id}"),
            ]]
        await self._send(
            row,
            OutboundMessage(text=str(result.get("message") or ""), buttons=buttons),
        )

    async def _handle_callback(self, callback: dict, external_id: str) -> None:
        callback_id = str(callback.get("id") or "")
        data = str(callback.get("data") or "")
        message = callback.get("message") or {}
        message_id = message.get("message_id")
        row = await self._channels.get_by_external("telegram", external_id)
        if row is None or row.status != "active":
            await self._answer(callback_id, "Link your account first.")
            return
        parsed = parse_callback(data)
        if parsed is None:
            await self._answer(callback_id, "Unknown action.")
            return
        kind, action_id = parsed
        if kind == "md":
            await self._delete_memory(action_id, row.user_id, callback_id, message_id, external_id)
            return
        if kind in ("d", "s10", "s60", "st"):
            await self._handle_reminder_callback(
                kind, action_id, row.user_id, callback_id, message_id, external_id
            )
            return
        if kind == "a":
            result = await self._orchestrator.approve_action(action_id, row.user_id)
        else:
            result = await self._orchestrator.reject_action(action_id, row.user_id)
        error = str(result.get("error") or "")
        if result.get("status_code"):
            if "not found" in error:
                notice = "That action is not yours."
            elif "expired" in error:
                notice = "That action has expired."
            else:
                notice = "Already handled."
            await self._answer(callback_id, notice)
            if isinstance(message_id, int) and self._telegram is not None:
                await self._telegram.edit_message(external_id, message_id, notice, rich=False)
            return
        await self._answer(callback_id)
        outcome = str(result.get("message") or "Done.")
        if isinstance(message_id, int) and self._telegram is not None:
            await self._telegram.edit_message(external_id, message_id, outcome)

    async def _memory_page(self, user_id: str, arg: str) -> OutboundMessage:
        if self._memory is None or not hasattr(self._memory, "list"):
            return OutboundMessage(text="Memory is not available.", format="plain")
        page = 1
        if arg.strip().isdigit():
            page = max(1, int(arg.strip()))
        page_size = 5
        rows = await self._memory.list(
            user_id, limit=page_size + 1, offset=(page - 1) * page_size
        )
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        if not rows:
            if page == 1:
                return OutboundMessage(text="I am not storing any memories yet.", format="plain")
            return OutboundMessage(text="No more memories.", format="plain")
        lines = [f"Memories, page {page}:"]
        buttons: list[list[Button]] = []
        for row in rows:
            lines.append(f"• [{row.kind}] {row.content}")
            label = row.content[:24]
            buttons.append([Button(text=f"Delete: {label}", callback_data=f"md:{row.id}")])
        if has_more:
            lines.append(f"Send /memory {page + 1} for the next page.")
        return OutboundMessage(text="\n".join(lines), buttons=buttons, format="plain")

    async def _forget(self, user_id: str, arg: str) -> OutboundMessage:
        text = arg.strip()
        if not text:
            return OutboundMessage(
                text="Send /forget followed by what to delete, for example /forget vegetarian.",
                format="plain",
            )
        if self._memory is None:
            return OutboundMessage(text="Memory is not available.", format="plain")
        finder = getattr(self._memory, "search_for_forget", None)
        if finder is None:
            matches = await self._memory.search(user_id, text, limit=5)
        else:
            matches = await finder(user_id, text, limit=5)
        if not matches:
            return OutboundMessage(text="I could not find a memory matching that.", format="plain")
        lines = ["Tap delete to forget these:"]
        buttons: list[list[Button]] = []
        for row in matches:
            lines.append(f"• {row.content}")
            buttons.append([Button(text=f"Delete: {row.content[:24]}", callback_data=f"md:{row.id}")])
        return OutboundMessage(text="\n".join(lines), buttons=buttons, format="plain")

    async def _delete_memory(
        self,
        memory_id: str,
        user_id: str,
        callback_id: str,
        message_id,
        external_id: str,
    ) -> None:
        if self._memory is None:
            await self._answer(callback_id, "Memory is not available.")
            return
        row = await self._memory.get(user_id, memory_id) if hasattr(self._memory, "get") else None
        if row is None:
            await self._answer(callback_id, "That memory is already gone.")
            return
        await self._memory.delete(user_id, memory_id)
        notice = f"Forgot: {row.content}"
        await self._answer(callback_id, "Deleted.")
        if isinstance(message_id, int) and self._telegram is not None:
            await self._telegram.edit_message(external_id, message_id, notice, rich=False)

    async def _brief(self, user_id: str) -> OutboundMessage:
        if self._briefs is None:
            return OutboundMessage(text="The morning brief is not available yet.", format="plain")
        result = await self._briefs.run(user_id, now=self._now(), immediate=True)
        if result.channel == "telegram" and result.status in ("sent", "deduped"):
            return OutboundMessage(text="Sent your morning brief.", format="plain")
        if result.status == "failed":
            return OutboundMessage(text="I couldn't send the brief. Try again in a minute.", format="plain")
        return OutboundMessage(text=result.text or "Nothing due today.", format="plain")

    async def _handle_reminder_callback(
        self,
        kind: str,
        reminder_id: str,
        user_id: str,
        callback_id: str,
        message_id,
        external_id: str,
    ) -> None:
        if self._reminders is None:
            await self._answer(callback_id, "Reminders are unavailable.")
            return
        reminder = await self._reminders.get_for_user(user_id, reminder_id)
        if reminder is None:
            await self._answer(callback_id, "That reminder is not yours.")
            return
        if kind == "d":
            outcome = await complete_reminder(self._reminders, self._jobs, reminder)
        else:
            outcome = await snooze_reminder(
                self._reminders,
                self._jobs,
                reminder,
                kind=kind,
                now=self._now(),
            )
        if outcome.startswith("Error:"):
            await self._answer(callback_id, "Couldn't update that reminder.")
            return
        await self._answer(callback_id)
        if isinstance(message_id, int) and self._telegram is not None:
            await self._telegram.edit_message(external_id, message_id, outcome)

    async def _conversation_id(self, row: UserChannel) -> str:
        existing = await self._conversations.latest_channel_conversation(
            row.user_id, "telegram", row.external_id
        )
        if existing:
            return existing
        return await self._conversations.create_conversation(
            row.user_id, channel="telegram", channel_chat_id=row.external_id
        )

    async def _reply(self, external_id: str, text: str) -> None:
        channel = UserChannel(
            id="transient",
            user_id="",
            channel="telegram",
            external_id=external_id,
            external_username=None,
            status="active",
        )
        await self._send(channel, OutboundMessage(text=text, format="plain"))

    async def _send(self, row: UserChannel, msg: OutboundMessage) -> None:
        if self._telegram is None:
            logger.info("telegram outbound skipped; bot token is not configured")
            return
        result = await self._telegram.send(row, msg)
        if result.blocked:
            if row.user_id:
                await self._channels.set_status(row.user_id, "telegram", "blocked")
            logger.info("telegram chat blocked external_id=%s", row.external_id)

    async def _answer(self, callback_id: str, text: str | None = None) -> None:
        if self._telegram is None or not callback_id:
            return
        await self._telegram.answer_callback(callback_id, text)

    async def _lock_for(self, external_id: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(external_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[external_id] = lock
            return lock
