from datetime import datetime, timedelta, timezone

import pytest

from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.brief.sections import WeatherSection, next_brief_at
from jarvis_ai.brief.service import BriefService, InMemoryBriefRuns, default_sections
from jarvis_ai.channels.base import OutboundMessage, SendResult
from jarvis_ai.channels.memory import InMemoryChannelStore
from jarvis_ai.channels.parse import parse_callback
from jarvis_ai.channels.service import TelegramService
from jarvis_ai.channels.web import WebAdapter
from jarvis_ai.conversations.memory import InMemoryConversationsStore
from jarvis_ai.jobs.memory import InMemoryJobQueue
from jarvis_ai.jobs.reminder_fire import ReminderFireHandler
from jarvis_ai.jobs.worker import run_once
import jarvis_ai.policy.policy  # noqa: F401  # load policy before the tools package
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.notify.memory import InMemoryNotificationLog
from jarvis_ai.notify.service import NotifyService
from jarvis_ai.reminders.memory import InMemoryRemindersStore
from jarvis_ai.reminders.schedule import next_occurrence
from jarvis_ai.tools import build_default_registry
from jarvis_ai.tools.context import ToolContext
from jarvis_ai.user_settings.memory import InMemoryUserSettingsStore


FROZEN = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
REMINDER_ID = "33333333-3333-3333-3333-333333333333"


class CountingAdapter:
    name = "web"
    capabilities = WebAdapter.capabilities

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, user_channel, msg: OutboundMessage) -> SendResult:
        self.sent.append(msg)
        return SendResult(ok=True)


def _notifier(adapter: CountingAdapter, settings: InMemoryUserSettingsStore | None = None):
    return NotifyService(
        settings or InMemoryUserSettingsStore(),
        InMemoryNotificationLog(),
        {"web": adapter},
        InMemoryChannelStore(),
    )


def _freeze_set(monkeypatch, moment: datetime = FROZEN) -> None:
    monkeypatch.setattr("jarvis_ai.tools.set_reminder._now", lambda: moment)


@pytest.mark.asyncio
async def test_set_reminder_enqueues_one_fire(monkeypatch) -> None:
    _freeze_set(monkeypatch)
    reminders = InMemoryRemindersStore()
    jobs = InMemoryJobQueue()
    registry = build_default_registry()
    ctx = ToolContext(user_id="user-1", timezone="UTC", reminders=reminders, jobs=jobs)
    due = "2026-06-01T12:02:00Z"
    result = await registry.run("set_reminder", {"message": "call mom", "due_at": due}, ctx)
    assert "call mom" in result
    assert len(jobs.jobs) == 1
    job = next(iter(jobs.jobs.values()))
    assert job.kind == "reminder_fire"
    assert job.run_at == datetime(2026, 6, 1, 12, 2, tzinfo=timezone.utc)
    assert job.dedupe_key == f"reminder:{job.payload['reminder_id']}:2026-06-01T12:02:00Z"


@pytest.mark.asyncio
async def test_past_reminder_is_not_enqueued(monkeypatch) -> None:
    _freeze_set(monkeypatch)
    jobs = InMemoryJobQueue()
    ctx = ToolContext(
        user_id="user-1",
        reminders=InMemoryRemindersStore(),
        jobs=jobs,
    )
    result = await build_default_registry().run(
        "set_reminder",
        {"message": "too late", "due_at": "2026-06-01T11:00:00Z"},
        ctx,
    )
    assert "already passed" in result
    assert jobs.jobs == {}


@pytest.mark.asyncio
async def test_unknown_recurrence_asks_instead_of_guessing(monkeypatch) -> None:
    _freeze_set(monkeypatch)
    reminders = InMemoryRemindersStore()
    ctx = ToolContext(user_id="user-1", reminders=reminders, jobs=InMemoryJobQueue())
    result = await build_default_registry().run(
        "set_reminder",
        {"message": "stretch", "due_at": "2026-06-01T13:00:00Z", "recurrence": "every other day"},
        ctx,
    )
    assert "daily" in result
    assert reminders._items == []


@pytest.mark.asyncio
async def test_reminder_send_is_once_when_processed_twice() -> None:
    reminders = InMemoryRemindersStore()
    jobs = InMemoryJobQueue()
    adapter = CountingAdapter()
    handler = ReminderFireHandler(reminders, _notifier(adapter), jobs, clock=lambda: FROZEN)
    reminder_id = await reminders.create("user-1", "stand up", FROZEN, timezone="UTC")
    job = await jobs.enqueue(
        kind="reminder_fire",
        user_id="user-1",
        run_at=FROZEN,
        payload={"reminder_id": reminder_id, "occurrence_ts": "2026-06-01T12:00:00Z"},
        dedupe_key=f"reminder:{reminder_id}:2026-06-01T12:00:00Z",
    )
    await handler(job)
    await handler(job)
    assert len(adapter.sent) == 1
    assert adapter.sent[0].text == "stand up"
    stored = await reminders.get(reminder_id)
    assert stored is not None
    assert stored.status == "fired"


@pytest.mark.asyncio
async def test_cancelled_reminder_does_not_send() -> None:
    reminders = InMemoryRemindersStore()
    jobs = InMemoryJobQueue()
    adapter = CountingAdapter()
    handler = ReminderFireHandler(reminders, _notifier(adapter), jobs, clock=lambda: FROZEN)
    ctx = ToolContext(user_id="user-1", reminders=reminders, jobs=jobs)
    reminder_id = await reminders.create("user-1", "ignore me", FROZEN)
    await build_default_registry().run("cancel_reminder", {"reminder_id": reminder_id}, ctx)
    job = await jobs.enqueue(
        kind="reminder_fire",
        user_id="user-1",
        run_at=FROZEN,
        payload={"reminder_id": reminder_id, "occurrence_ts": "2026-06-01T12:00:00Z"},
        dedupe_key=f"reminder:{reminder_id}:other",
    )
    await handler(job)
    assert adapter.sent == []


@pytest.mark.asyncio
async def test_expired_lease_is_reclaimed_and_sends_once() -> None:
    reminders = InMemoryRemindersStore()
    jobs = InMemoryJobQueue()
    adapter = CountingAdapter()
    handler = ReminderFireHandler(reminders, _notifier(adapter), jobs, clock=lambda: FROZEN)
    reminder_id = await reminders.create("user-1", "reclaim", FROZEN)
    job = await jobs.enqueue(
        kind="reminder_fire",
        user_id="user-1",
        run_at=FROZEN,
        payload={"reminder_id": reminder_id, "occurrence_ts": "2026-06-01T12:00:00Z"},
        dedupe_key=f"reminder:{reminder_id}:2026-06-01T12:00:00Z",
    )
    job.status = "running"
    job.attempts = 1
    job.locked_until = FROZEN - timedelta(seconds=1)
    claimed = await run_once(jobs, {"reminder_fire": handler}, now=FROZEN, lease_seconds=60)
    assert claimed == 1
    assert len(adapter.sent) == 1
    assert jobs.jobs[job.id].status == "done"


@pytest.mark.asyncio
async def test_late_delivery_prefixes_the_original_local_time() -> None:
    reminders = InMemoryRemindersStore()
    adapter = CountingAdapter()
    late = FROZEN + timedelta(minutes=3)
    handler = ReminderFireHandler(reminders, _notifier(adapter), InMemoryJobQueue(), clock=lambda: late)
    reminder_id = await reminders.create("user-1", "medicine", FROZEN, timezone="UTC")
    job = await InMemoryJobQueue().enqueue(
        kind="reminder_fire",
        user_id="user-1",
        run_at=FROZEN,
        payload={"reminder_id": reminder_id, "occurrence_ts": "2026-06-01T12:00:00Z"},
        dedupe_key=f"reminder:{reminder_id}:2026-06-01T12:00:00Z",
    )
    await handler(job)
    assert adapter.sent[0].text.startswith("Late reminder (originally")
    assert "medicine" in adapter.sent[0].text
    assert all(len(button.callback_data) <= 64 for row in adapter.sent[0].buttons or [] for button in row)


def test_daily_recurrence_stays_at_nine_across_dst() -> None:
    start = datetime(2026, 3, 7, 14, 0, tzinfo=timezone.utc)  # 09:00 EST
    nxt = next_occurrence("FREQ=DAILY", start, "America/New_York")
    assert nxt == datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc)  # 09:00 EDT


def test_brief_time_follows_the_local_clock_across_dst() -> None:
    before = datetime(2026, 3, 7, 10, 0, tzinfo=timezone.utc)
    after = datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc)
    assert next_brief_at(before, "America/New_York", "08:00") == datetime(2026, 3, 7, 13, 0, tzinfo=timezone.utc)
    assert next_brief_at(after, "America/New_York", "08:00") == datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
    kolkata = datetime(2026, 6, 1, 1, 0, tzinfo=timezone.utc)
    assert next_brief_at(kolkata, "Asia/Kolkata", "08:00") == datetime(2026, 6, 1, 2, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_scheduled_brief_is_one_per_local_day_and_command_is_not() -> None:
    settings = InMemoryUserSettingsStore()
    cfg = await settings.get("user-1")
    cfg.brief_enabled = True
    cfg.brief_time_local = "08:00"
    cfg.timezone = "UTC"
    reminders = InMemoryRemindersStore()
    await reminders.create(
        "user-1",
        "dentist",
        datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        timezone="UTC",
    )
    pending = InMemoryPendingActionsStore()
    await pending.create("user-1", "call-1", "save_note", {"content": "passport"}, [])
    adapter = CountingAdapter()
    jobs = InMemoryJobQueue()
    service = BriefService(
        settings_store=settings,
        notifier=_notifier(adapter, settings),
        runs=InMemoryBriefRuns(),
        jobs=jobs,
        sections=default_sections(reminders, pending),
        clock=lambda: FROZEN,
    )
    first = await service.run("user-1", now=FROZEN, immediate=False)
    second = await service.run("user-1", now=FROZEN, immediate=False)
    assert first.status == "sent"
    assert "dentist" in first.text
    assert "passport" in first.text
    assert second.status == "deduped"
    assert len(adapter.sent) == 1

    immediate = await service.run("user-1", now=FROZEN, immediate=True)
    assert immediate.status == "sent"
    assert len(adapter.sent) == 2
    assert await jobs.has_pending(kind="daily_brief", user_id="user-1")


@pytest.mark.asyncio
async def test_brief_section_failure_still_sends_the_rest() -> None:
    class Boom:
        key = "boom"
        title = "Broken"

        async def collect(self, ctx):
            raise RuntimeError("section down")

    settings = InMemoryUserSettingsStore()
    await settings.get("user-1")
    adapter = CountingAdapter()
    service = BriefService(
        settings_store=settings,
        notifier=_notifier(adapter, settings),
        runs=InMemoryBriefRuns(),
        jobs=InMemoryJobQueue(),
        sections=[Boom(), WeatherSection()],
        section_timeout=0.05,
    )
    result = await service.run("user-1", now=FROZEN, immediate=True)
    assert result.status == "sent"
    assert "Nothing due today." in result.text
    assert "Broken" not in result.text


@pytest.mark.asyncio
async def test_weather_section_is_empty_without_a_city() -> None:
    settings = await InMemoryUserSettingsStore().get("user-1")
    from jarvis_ai.brief.sections import BriefContext

    assert await WeatherSection().collect(BriefContext("user-1", FROZEN, settings)) is None
    settings.brief_sections["weather"] = True
    settings.feature_flags["weather_city"] = "Bengaluru"
    assert await WeatherSection().collect(BriefContext("user-1", FROZEN, settings)) is None


@pytest.mark.asyncio
async def test_rewrite_failure_sends_the_template() -> None:
    class BadLLM:
        name = "openai"

        async def complete(self, message, system=None):
            raise RuntimeError("model down")

    settings = InMemoryUserSettingsStore()
    await settings.get("user-1")
    adapter = CountingAdapter()
    service = BriefService(
        settings_store=settings,
        notifier=_notifier(adapter, settings),
        runs=InMemoryBriefRuns(),
        jobs=InMemoryJobQueue(),
        sections=[],
        llm=BadLLM(),
    )
    result = await service.run("user-1", now=FROZEN, immediate=True)
    assert result.text.startswith("Morning brief")
    assert adapter.sent[0].text == result.text


def test_reminder_callbacks_fit_telegram_limit() -> None:
    assert parse_callback(f"d:{REMINDER_ID}") == ("d", REMINDER_ID)
    assert parse_callback(f"s10:{REMINDER_ID}") == ("s10", REMINDER_ID)
    assert parse_callback(f"s60:{REMINDER_ID}") == ("s60", REMINDER_ID)
    assert parse_callback(f"st:{REMINDER_ID}") == ("st", REMINDER_ID)
    assert parse_callback(f"s10:not-a-uuid") is None
    assert len(f"s60:{REMINDER_ID}") <= 64


class _RecordingTelegram:
    def __init__(self) -> None:
        self.edits: list[str] = []
        self.answers: list[str | None] = []

    async def edit_message(self, chat_id: str, message_id: int, text: str, *, rich: bool = True) -> SendResult:
        self.edits.append(text)
        return SendResult(ok=True)

    async def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        self.answers.append(text)


class _Orchestrator:
    async def chat(self, *args, **kwargs):
        return {"message": "ok"}

    async def approve_action(self, action_id: str, user_id: str | None):
        return {"message": "ok"}

    async def reject_action(self, action_id: str, user_id: str | None):
        return {"message": "cancelled"}


@pytest.mark.asyncio
async def test_done_and_foreign_snooze_callbacks() -> None:
    reminders = InMemoryRemindersStore()
    jobs = InMemoryJobQueue()
    own_id = await reminders.create("user-1", "stretch", FROZEN + timedelta(hours=1))
    other_id = await reminders.create("user-2", "secret", FROZEN + timedelta(hours=2))
    await jobs.enqueue(
        kind="reminder_fire",
        user_id="user-1",
        run_at=FROZEN + timedelta(hours=1),
        payload={"reminder_id": own_id, "occurrence_ts": "2026-06-01T13:00:00Z"},
        dedupe_key=f"reminder:{own_id}:2026-06-01T13:00:00Z",
    )
    telegram = _RecordingTelegram()
    channels = InMemoryChannelStore()
    svc = TelegramService(
        channels=channels,
        conversations=InMemoryConversationsStore(),
        orchestrator=_Orchestrator(),
        telegram=telegram,
        settings_store=InMemoryUserSettingsStore(),
        notes=InMemoryNotesStore(),
        reminders=reminders,
        bot_username="jarvis_bot",
        jobs=jobs,
        clock=lambda: FROZEN,
    )
    await channels.link("user-1", "telegram", "7", None, FROZEN)
    await svc.handle_update(
        {
            "update_id": 1,
            "callback_query": {
                "id": "cb-1",
                "data": f"d:{own_id}",
                "message": {"message_id": 9, "chat": {"id": 7}},
            },
        }
    )
    done = await reminders.get(own_id)
    assert done is not None and done.status == "done"
    assert telegram.edits[-1] == "Marked done."
    assert all(job.status == "cancelled" for job in jobs.jobs.values())

    await svc.handle_update(
        {
            "update_id": 2,
            "callback_query": {
                "id": "cb-2",
                "data": f"s10:{other_id}",
                "message": {"message_id": 9, "chat": {"id": 7}},
            },
        }
    )
    assert telegram.answers[-1] == "That reminder is not yours."
    untouched = await reminders.get(other_id)
    assert untouched is not None and untouched.status == "scheduled"


@pytest.mark.asyncio
async def test_recurring_fire_enqueues_the_next_local_occurrence() -> None:
    reminders = InMemoryRemindersStore()
    jobs = InMemoryJobQueue()
    adapter = CountingAdapter()
    start = datetime(2026, 3, 7, 14, 0, tzinfo=timezone.utc)
    handler = ReminderFireHandler(reminders, _notifier(adapter), jobs, clock=lambda: start)
    reminder_id = await reminders.create(
        "user-1",
        "standup",
        start,
        timezone="America/New_York",
        rrule="FREQ=DAILY",
    )
    job = await jobs.enqueue(
        kind="reminder_fire",
        user_id="user-1",
        run_at=start,
        payload={"reminder_id": reminder_id, "occurrence_ts": "2026-03-07T14:00:00Z"},
        dedupe_key=f"reminder:{reminder_id}:2026-03-07T14:00:00Z",
    )
    await handler(job)
    stored = await reminders.get(reminder_id)
    assert stored is not None
    assert stored.due_at == datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc)
    assert stored.status == "scheduled"
    nxt = [item for item in jobs.jobs.values() if item.id != job.id]
    assert len(nxt) == 1
    assert nxt[0].run_at == stored.due_at


@pytest.mark.asyncio
async def test_quiet_hours_skip_the_scheduled_brief() -> None:
    settings = InMemoryUserSettingsStore()
    cfg = await settings.get("user-1")
    cfg.quiet_hours_start = "00:00"
    cfg.quiet_hours_end = "23:59"
    adapter = CountingAdapter()
    service = BriefService(
        settings_store=settings,
        notifier=_notifier(adapter, settings),
        runs=InMemoryBriefRuns(),
        jobs=InMemoryJobQueue(),
        sections=[],
    )
    result = await service.run("user-1", now=FROZEN, immediate=False)
    assert result.status == "skipped"
    assert adapter.sent == []
