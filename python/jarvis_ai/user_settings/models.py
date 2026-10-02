from dataclasses import dataclass, field
from typing import Any


def default_brief_sections() -> dict[str, bool]:
    return {
        "reminders": True,
        "calendar": True,
        "email": True,
        "weather": False,
    }


@dataclass
class UserSettings:
    timezone: str = "UTC"
    locale: str = "en"
    preferred_channel: str = "web"
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    brief_enabled: bool = True
    brief_time_local: str = "08:00"
    brief_sections: dict[str, bool] = field(default_factory=default_brief_sections)
    feature_flags: dict[str, Any] = field(default_factory=dict)
