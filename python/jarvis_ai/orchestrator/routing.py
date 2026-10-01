"""Simple routing helpers — Phase 2.3 (before LLM picks tools)."""

import re
from datetime import datetime, timezone
from typing import Any

# Matches: "calculate 2+2", "calc 99*101"
_CALC_PREFIX = re.compile(r"^(?:calculate|calc)\s+(.+)$", re.IGNORECASE)

# Matches bare math like "99*101" or "(10+5)/3"
_MATH_CHARS = re.compile(r"^[\d\s+\-*/().%]+$")

# "what is 847 times 293", "847 times 293", "847 x 293"
_NATURAL_MUL = re.compile(
    r"^(?:what(?:'s| is)\s+)?(\d[\d,]*)\s*(?:times|multiplied by|×|\*|x)\s*(\d[\d,]*)\s*\??$",
    re.IGNORECASE,
)


def _strip_commas(num: str) -> str:
    return num.replace(",", "").strip()


def try_extract_calculator_expression(message: str) -> str | None:
    """
    Return a math expression if this message should use the calculator tool.

    Examples that match:
      - "calculate 2+2"
      - "calc 99*101"
      - "15*0.2"   (bare expression)

    Examples that do not match:
      - "hello"
      - "what is 2+2?"  (LLM will handle in 2.4)
    """
    text = message.strip()
    if not text:
        return None

    prefix_match = _CALC_PREFIX.match(text)
    if prefix_match:
        return prefix_match.group(1).strip()

    mul_match = _NATURAL_MUL.match(text)
    if mul_match:
        left = _strip_commas(mul_match.group(1))
        right = _strip_commas(mul_match.group(2))
        return f"{left}*{right}"

    if _MATH_CHARS.match(text) and any(op in text for op in "+-*/"):
        return text

    return None


_MONTHS: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_SAVE_NOTE = re.compile(r"^save a note:\s*(.+)$", re.IGNORECASE)

_REMIND_ME = re.compile(
    r"^remind me (?:to\s+)?(.+?)\s+(?:on|at)\s+(.+)$",
    re.IGNORECASE,
)

_APPT_IS_ON = re.compile(
    r"^(?:my\s+)?(.+?)\s+is\s+on\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\s*\.?$",
    re.IGNORECASE,
)


def _parse_clock_hour(hour: int, minute: int, ampm: str | None) -> tuple[int, int]:
    if ampm:
        ampm = ampm.lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
    return hour, minute


def _next_occurrence_utc(month: int, day: int, hour: int, minute: int) -> datetime:
    now = datetime.now(timezone.utc)
    year = now.year
    due = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    if due < now:
        due = datetime(year + 1, month, day, hour, minute, tzinfo=timezone.utc)
    return due


def _parse_month_day_time(
    month_name: str,
    day_str: str,
    hour_str: str | None,
    min_str: str | None,
    ampm: str | None,
) -> str | None:
    month = _MONTHS.get(month_name.lower())
    if not month:
        return None
    day = int(day_str)
    hour = int(hour_str) if hour_str else 9
    minute = int(min_str) if min_str else 0
    hour, minute = _parse_clock_hour(hour, minute, ampm)
    due = _next_occurrence_utc(month, day, hour, minute)
    return due.isoformat().replace("+00:00", "Z")


def try_extract_save_note_content(message: str) -> str | None:
    text = message.strip()
    match = _SAVE_NOTE.match(text)
    if not match:
        return None
    content = match.group(1).strip()
    return content or None


def try_extract_set_reminder_args(message: str) -> dict[str, Any] | None:
    """
    Build set_reminder arguments from natural language (no LLM required).

    Examples:
      - "my dentist is on April 12 at 3pm"
      - "Remind me to call mom on October 3, 2026 at 9:00 AM"
    """
    text = message.strip()
    if not text:
        return None

    appt = _APPT_IS_ON.match(text)
    if appt:
        subject = appt.group(1).strip().title()
        due_at = _parse_month_day_time(
            appt.group(2),
            appt.group(3),
            appt.group(4),
            appt.group(5),
            appt.group(6),
        )
        if not due_at:
            return None
        return {
            "message": f"{subject} appointment",
            "due_at": due_at,
        }

    remind = _REMIND_ME.match(text)
    if remind:
        body = remind.group(1).strip()
        when = remind.group(2).strip()
        iso_match = re.search(
            r"(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{1,2}):(\d{2}))?",
            when,
        )
        if iso_match:
            year, mon, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            hour = int(iso_match.group(4)) if iso_match.group(4) else 9
            minute = int(iso_match.group(5)) if iso_match.group(5) else 0
            due = datetime(year, mon, day, hour, minute, tzinfo=timezone.utc)
            return {"message": body, "due_at": due.isoformat().replace("+00:00", "Z")}

        month_day = re.match(
            r"(january|february|march|april|may|june|july|august|september|october|november|december)"
            r"\s+(\d{1,2})(?:st|nd|rd|th)?"
            r"(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
            when,
            re.IGNORECASE,
        )
        if month_day:
            due_at = _parse_month_day_time(
                month_day.group(1),
                month_day.group(2),
                month_day.group(3),
                month_day.group(4),
                month_day.group(5),
            )
            if due_at:
                return {"message": body, "due_at": due_at}

    return None
