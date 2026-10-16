"""When a reminder fires, and how a repeat phrase becomes an RRULE."""

import re
from datetime import datetime, timedelta, timezone

from dateutil.rrule import rrulestr

from jarvis_ai.user_settings.tz import resolve_zone

LATE_AFTER = timedelta(minutes=2)

_WEEKDAYS = {
    "monday": "MO",
    "tuesday": "TU",
    "wednesday": "WE",
    "thursday": "TH",
    "friday": "FR",
    "saturday": "SA",
    "sunday": "SU",
}

ASK_RECURRENCE = (
    "I can repeat a reminder daily, on weekdays, weekly, or monthly. "
    "Which of those should I use?"
)


def occurrence_token(due_at: datetime) -> str:
    utc = _as_utc(due_at).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def reminder_dedupe_key(reminder_id: str, due_at: datetime) -> str:
    return f"reminder:{reminder_id}:{occurrence_token(due_at)}"


def parse_occurrence(token: str) -> datetime | None:
    text = token.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def recurrence_to_rrule(phrase: str, due_local: datetime) -> str | None:
    """Map a small set of phrases to an RRULE. Unknown phrases return None."""
    text = " ".join(phrase.strip().lower().split())
    if not text:
        return ""
    if text in {"daily", "every day", "everyday"}:
        return "FREQ=DAILY"
    if text in {"weekdays", "every weekday", "week days"}:
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    if text in {"weekly", "every week"}:
        code = _weekday_code(due_local)
        return f"FREQ=WEEKLY;BYDAY={code}"
    if text in {"monthly", "every month", "monthly on this date"}:
        return f"FREQ=MONTHLY;BYMONTHDAY={due_local.day}"

    weekly = re.fullmatch(r"(?:every|weekly on|weekly)\s+([a-z]+)", text)
    if weekly and weekly.group(1) in _WEEKDAYS:
        return f"FREQ=WEEKLY;BYDAY={_WEEKDAYS[weekly.group(1)]}"
    return None


def next_occurrence(rrule: str, previous_utc: datetime, tz_name: str) -> datetime | None:
    """Next fire after `previous_utc`, keeping the local wall clock across DST."""
    tz = resolve_zone(tz_name)
    previous_local = _as_utc(previous_utc).astimezone(tz).replace(tzinfo=None)
    rule = rrulestr(rrule, dtstart=previous_local)
    nxt = rule.after(previous_local)
    if nxt is None:
        return None
    aware = nxt.replace(tzinfo=tz)
    return aware.astimezone(timezone.utc)


def first_future(
    due_at: datetime,
    *,
    now: datetime,
    rrule: str | None,
    tz_name: str,
) -> datetime | None:
    """The due time itself when it is still ahead, otherwise the next repeat."""
    cursor = _as_utc(due_at)
    moment = _as_utc(now)
    if cursor > moment:
        return cursor
    if not rrule:
        return None
    for _ in range(366 * 5):
        nxt = next_occurrence(rrule, cursor, tz_name)
        if nxt is None or nxt <= cursor:
            return None
        if nxt > moment:
            return nxt
        cursor = nxt
    return None


def snooze_until(kind: str, *, now: datetime, due_at: datetime, tz_name: str) -> datetime | None:
    moment = _as_utc(now)
    if kind in {"s10", "10", "10m"}:
        return moment + timedelta(minutes=10)
    if kind in {"s60", "60", "1h", "60m"}:
        return moment + timedelta(minutes=60)
    if kind not in {"st", "tomorrow"}:
        return None
    tz = resolve_zone(tz_name)
    local_now = moment.astimezone(tz)
    clock = _as_utc(due_at).astimezone(tz)
    tomorrow = (local_now + timedelta(days=1)).date()
    target = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        clock.hour,
        clock.minute,
        clock.second,
        tzinfo=tz,
    )
    if target <= local_now:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def is_late(run_at: datetime, now: datetime) -> bool:
    return _as_utc(now) - _as_utc(run_at) > LATE_AFTER


def _weekday_code(due_local: datetime) -> str:
    return ("MO", "TU", "WE", "TH", "FR", "SA", "SU")[due_local.weekday()]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
