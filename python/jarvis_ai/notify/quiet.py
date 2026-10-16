from datetime import datetime


def in_quiet_hours(now_local: datetime, start: str | None, end: str | None) -> bool:
    """True when local clock time falls inside the quiet window. Overnight windows wrap."""
    if not start or not end:
        return False
    start_min = _minutes(start)
    end_min = _minutes(end)
    if start_min is None or end_min is None or start_min == end_min:
        return False
    current = now_local.hour * 60 + now_local.minute
    if start_min < end_min:
        return start_min <= current < end_min
    return current >= start_min or current < end_min


def _minutes(value: str) -> int | None:
    parts = value.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute
