from datetime import datetime

from jarvis_ai.user_settings.tz import resolve_zone


def format_datetime_local(dt: datetime, timezone: str) -> str:
    """Human-readable local time for confirmations and prompts."""
    tz = resolve_zone(timezone)
    if dt.tzinfo is None:
        from datetime import timezone as tz_mod

        dt = dt.replace(tzinfo=tz_mod.utc)
    local = dt.astimezone(tz)
    clock = local.strftime("%I:%M %p").lstrip("0")
    tz_label = local.tzname() or timezone
    return f"{local.strftime('%a %d %b %Y')}, {clock} {tz_label}"


def now_local_iso(timezone: str) -> str:
    tz = resolve_zone(timezone)
    return datetime.now(tz).strftime("%A %Y-%m-%d %H:%M %Z")
