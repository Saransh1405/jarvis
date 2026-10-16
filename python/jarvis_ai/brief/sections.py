"""Morning-brief sections. A section that fails or times out contributes nothing."""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Protocol

from jarvis_ai.user_settings.formatting import format_datetime_local
from jarvis_ai.user_settings.models import UserSettings
from jarvis_ai.user_settings.tz import resolve_zone

logger = logging.getLogger(__name__)


@dataclass
class BriefContext:
    user_id: str
    now: datetime
    settings: UserSettings


class BriefSection(Protocol):
    key: str
    title: str

    async def collect(self, ctx: BriefContext) -> str | None: ...


class RemindersTodaySection:
    key = "reminders_today"
    title = "Reminders today"

    def __init__(self, reminders) -> None:
        self._reminders = reminders

    async def collect(self, ctx: BriefContext) -> str | None:
        if not ctx.settings.brief_sections.get("reminders", True):
            return None
        start, end = _local_day(ctx.now, ctx.settings.timezone, offset_days=0)
        items = await self._reminders.list_between(ctx.user_id, start, end)
        return _reminder_lines(items, ctx.settings.timezone)


class MissedRemindersSection:
    key = "missed"
    title = "Missed since yesterday"

    def __init__(self, reminders) -> None:
        self._reminders = reminders

    async def collect(self, ctx: BriefContext) -> str | None:
        if not ctx.settings.brief_sections.get("reminders", True):
            return None
        start, end = _local_day(ctx.now, ctx.settings.timezone, offset_days=-1)
        items = await self._reminders.list_between(
            ctx.user_id,
            start,
            end,
            statuses=("scheduled", "snoozed", "missed"),
        )
        return _reminder_lines(items, ctx.settings.timezone)


class PendingApprovalsSection:
    key = "approvals"
    title = "Pending approvals"

    def __init__(self, pending) -> None:
        self._pending = pending

    async def collect(self, ctx: BriefContext) -> str | None:
        if self._pending is None:
            return None
        rows = await self._pending.list_pending(ctx.user_id, limit=10)
        if not rows:
            return None
        lines = []
        for row in rows:
            summary = _arg_summary(row.arguments)
            if summary:
                lines.append(f"• {row.tool_name}: {summary}")
            else:
                lines.append(f"• {row.tool_name}")
        return "\n".join(lines)


class WeatherSection:
    """Present so a later weather source can be dropped in without changing the generator."""

    key = "weather"
    title = "Weather"

    async def collect(self, ctx: BriefContext) -> str | None:
        if not ctx.settings.brief_sections.get("weather", False):
            return None
        city = ctx.settings.feature_flags.get("weather_city")
        if not isinstance(city, str) or not city.strip():
            return None
        return None


def render_brief(parts: list[tuple[str, str | None]], when_label: str) -> str:
    lines = [f"Morning brief — {when_label}"]
    wrote = False
    for title, body in parts:
        if not body:
            continue
        wrote = True
        lines.append("")
        lines.append(title)
        lines.append(body)
    if not wrote:
        lines.append("")
        lines.append("Nothing due today.")
    return "\n".join(lines)


def next_brief_at(now_utc: datetime, tz_name: str, brief_time_local: str) -> datetime:
    tz = resolve_zone(tz_name)
    local_now = now_utc.astimezone(tz)
    hour, minute = _parse_hhmm(brief_time_local)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def local_date(now_utc: datetime, tz_name: str):
    return now_utc.astimezone(resolve_zone(tz_name)).date()


def _local_day(now_utc: datetime, tz_name: str, *, offset_days: int) -> tuple[datetime, datetime]:
    tz = resolve_zone(tz_name)
    local = now_utc.astimezone(tz)
    start_day = local.date() + timedelta(days=offset_days)
    start = datetime.combine(start_day, time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def _reminder_lines(items, tz_name: str) -> str | None:
    if not items:
        return None
    return "\n".join(
        f"• {item.message} — {format_datetime_local(item.due_at, item.timezone or tz_name)}"
        for item in items
    )


def _arg_summary(arguments: dict) -> str:
    for key in ("message", "content", "title"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_text, _, minute_text = value.partition(":")
    try:
        hour = int(hour_text)
        minute = int(minute_text or "0")
    except ValueError:
        return 8, 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return 8, 0
    return hour, minute
