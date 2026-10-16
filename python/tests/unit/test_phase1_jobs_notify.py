from datetime import datetime, timedelta, timezone

import pytest

from jarvis_ai.channels.base import OutboundMessage, SendResult
from jarvis_ai.channels.memory import InMemoryChannelStore
from jarvis_ai.channels.web import WebAdapter
from jarvis_ai.jobs.memory import InMemoryJobQueue
from jarvis_ai.jobs.models import backoff_seconds
from jarvis_ai.jobs.worker import ping_handler, run_once
from jarvis_ai.notify.memory import InMemoryNotificationLog
from jarvis_ai.notify.quiet import in_quiet_hours
from jarvis_ai.notify.service import NotifyService
from jarvis_ai.user_settings.memory import InMemoryUserSettingsStore


def test_backoff_schedule() -> None:
    assert backoff_seconds(1) == 30
    assert backoff_seconds(2) == 120
    assert backoff_seconds(3) == 600
    assert backoff_seconds(4) == 3600
    assert backoff_seconds(9) == 3600


def test_quiet_hours_wrap_overnight() -> None:
    late = datetime(2026, 1, 1, 23, 0)
    morning = datetime(2026, 1, 1, 8, 0)
    assert in_quiet_hours(late, "22:00", "07:00") is True
    assert in_quiet_hours(morning, "22:00", "07:00") is False


@pytest.mark.asyncio
async def test_job_retries_then_is_reclaimed_after_the_lease_expires() -> None:
    queue = InMemoryJobQueue()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    job = await queue.enqueue(
        kind="ping",
        user_id="user-1",
        run_at=now,
        payload={"fail": True},
        max_attempts=3,
    )
    await run_once(queue, {"ping": ping_handler}, now=now, lease_seconds=60)
    stored = queue.jobs[job.id]
    assert stored.status == "scheduled"
    assert stored.attempts == 1
    assert stored.run_at > now

    await run_once(queue, {"ping": ping_handler}, now=now, lease_seconds=60)
    assert stored.attempts == 1

    stored.status = "running"
    stored.locked_until = now - timedelta(seconds=1)
    stored.run_at = now
    await run_once(queue, {"ping": ping_handler}, now=now, lease_seconds=60)
    assert stored.attempts == 2
    assert stored.status == "scheduled"


@pytest.mark.asyncio
async def test_notify_dedupes_a_repeated_key() -> None:
    class CountingAdapter:
        name = "web"
        capabilities = WebAdapter.capabilities

        def __init__(self) -> None:
            self.sends = 0

        async def send(self, user_channel, msg: OutboundMessage) -> SendResult:
            self.sends += 1
            return SendResult(ok=True)

    adapter = CountingAdapter()
    service = NotifyService(
        InMemoryUserSettingsStore(),
        InMemoryNotificationLog(),
        {"web": adapter},
        InMemoryChannelStore(),
    )
    message = OutboundMessage(text="hello", format="plain")
    first = await service.notify("user-1", "system", message, dedupe_key="note:1")
    second = await service.notify("user-1", "system", message, dedupe_key="note:1")
    assert first.status == "sent"
    assert second.status == "deduped"
    assert adapter.sends == 1
