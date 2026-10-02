from zoneinfo import ZoneInfo

# Browsers and older systems may still report deprecated IDs.
_TIMEZONE_ALIASES: dict[str, str] = {
    "asia/calcutta": "Asia/Kolkata",
}


def canonical_timezone(name: str) -> str:
    key = name.strip()
    if not key:
        return "UTC"
    return _TIMEZONE_ALIASES.get(key.lower(), key)


def resolve_zone(name: str) -> ZoneInfo:
    canonical = canonical_timezone(name)
    try:
        return ZoneInfo(canonical)
    except Exception:
        return ZoneInfo("UTC")
