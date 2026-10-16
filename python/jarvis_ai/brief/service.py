"""Compose a morning brief and deliver at most one scheduled copy per local day."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from jarvis_ai.brief.sections import (
    BriefContext,
    BriefSection,
    MissedRemindersSection,
    PendingApprovalsSection,
    RemindersTodaySection,
    WeatherSection,
    local_date,
    next_brief_at,
    render_brief,
)
from jarvis_ai.channels.base import OutboundMessage
from jarvis_ai.jobs.models import ScheduledJob
from jarvis_ai.user_settings.formatting import format_datetime_local

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM = (
    "Rewrite this morning brief as a short spoken update. "
    "Keep every fact. Do not add events, weather, or names that are not in the brief."
)


@dataclass
class BriefResult:
    text: str
    status: str
    channel: str | None = None


class BriefService:
    def __init__(
        self,
        *,
        settings_store,
        notifier,
        runs,
        jobs,
        sections: list[BriefSection],
        llm=None,
        clock: Callable[[], datetime] | None = None,
        section_timeout: float = 5,
        rewrite_timeout: float = 5,
    ) -> None:
        self._settings = settings_store
        self._notifier = notifier
        self._runs = runs
        self._jobs = jobs
        self._sections = sections
        self._llm = llm
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._section_timeout = section_timeout
        self._rewrite_timeout = rewrite_timeout

    async def handle(self, job: ScheduledJob) -> None:
        await self.run(job.user_id, now=self._clock(), immediate=False)

    async def run(self, user_id: str, *, now: datetime | None = None, immediate: bool = False) -> BriefResult:
        moment = now or self._clock()
        settings = await self._settings.get(user_id)
        day = local_date(moment, settings.timezone)
        if not immediate and not settings.brief_enabled:
            await self._runs.record(user_id=user_id, local_date=day, status="skipped", dedupe_key=None)
            return BriefResult(text="", status="skipped")

        template = await self.compose(user_id, moment, settings)
        text = await self._rewrite(template)
        dedupe_key = None if immediate else f"brief:{user_id}:{day.isoformat()}"
        result = await self._notifier.notify(
            user_id,
            "brief",
            OutboundMessage(text=text, format="plain"),
            dedupe_key=dedupe_key,
            bypass_quiet_hours=immediate,
        )
        await self._runs.record(
            user_id=user_id,
            local_date=day,
            status=result.status if result.status in ("sent", "skipped", "failed", "deduped") else "failed",
            dedupe_key=dedupe_key,
            error=result.error,
        )
        if not immediate and result.status != "failed":
            await self.enqueue_next(user_id, settings, moment)
        if result.status == "failed" and not immediate:
            raise RuntimeError(result.error or "brief notify failed")
        return BriefResult(text=text, status=result.status, channel=result.channel)

    async def compose(self, user_id: str, now: datetime, settings) -> str:
        ctx = BriefContext(user_id=user_id, now=now, settings=settings)
        parts: list[tuple[str, str | None]] = []
        for section in self._sections:
            body = await self._collect(section, ctx)
            parts.append((section.title, body))
        when = format_datetime_local(now, settings.timezone)
        return render_brief(parts, when)

    async def enqueue_next(self, user_id: str, settings, now: datetime) -> None:
        run_at = next_brief_at(now, settings.timezone, settings.brief_time_local)
        day = local_date(run_at, settings.timezone)
        await self._jobs.enqueue(
            kind="daily_brief",
            user_id=user_id,
            run_at=run_at,
            payload={"local_date": day.isoformat()},
            dedupe_key=f"brief:{user_id}:{day.isoformat()}",
        )

    async def ensure_scheduled(self, now: datetime | None = None) -> None:
        moment = now or self._clock()
        for user_id, settings in await self._settings.list_brief_enabled():
            if await self._jobs.has_pending(kind="daily_brief", user_id=user_id):
                continue
            await self.enqueue_next(user_id, settings, moment)

    async def _collect(self, section: BriefSection, ctx: BriefContext) -> str | None:
        try:
            return await asyncio.wait_for(section.collect(ctx), timeout=self._section_timeout)
        except Exception:
            logger.exception("brief section %s failed", section.key)
            return None

    async def _rewrite(self, text: str) -> str:
        llm = self._llm
        if llm is None or getattr(llm, "name", "stub") == "stub":
            return text
        try:
            rewritten = await asyncio.wait_for(
                llm.complete(text, system=_REWRITE_SYSTEM),
                timeout=self._rewrite_timeout,
            )
        except Exception:
            logger.exception("brief rewrite failed")
            return text
        cleaned = rewritten.strip() if isinstance(rewritten, str) else ""
        return cleaned or text


def default_sections(reminders, pending) -> list[BriefSection]:
    return [
        RemindersTodaySection(reminders),
        MissedRemindersSection(reminders),
        PendingApprovalsSection(pending),
        WeatherSection(),
    ]


class InMemoryBriefRuns:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def record(
        self,
        *,
        user_id: str,
        local_date,
        status: str,
        dedupe_key: str | None = None,
        error: str | None = None,
    ) -> None:
        self.rows.append(
            {
                "user_id": user_id,
                "local_date": local_date,
                "status": status,
                "dedupe_key": dedupe_key,
                "error": error,
            }
        )


class BriefRunsRepository:
    def __init__(self, pool) -> None:
        self._pool = pool

    async def record(
        self,
        *,
        user_id: str,
        local_date,
        status: str,
        dedupe_key: str | None = None,
        error: str | None = None,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO brief_runs (user_id, local_date, status, dedupe_key, error)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            local_date,
            status,
            dedupe_key,
            error,
        )
