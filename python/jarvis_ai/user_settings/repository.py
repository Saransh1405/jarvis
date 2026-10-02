import json
import logging
from typing import Any, Protocol

import asyncpg

from jarvis_ai.user_settings.models import UserSettings, default_brief_sections

logger = logging.getLogger(__name__)


class UserSettingsStore(Protocol):
    async def get(self, user_id: str) -> UserSettings: ...


class UserSettingsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, user_id: str) -> UserSettings:
        try:
            await self._pool.execute(
                """
                INSERT INTO user_settings (user_id)
                VALUES ($1::uuid)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
            )
            record = await self._pool.fetchrow(
                """
                SELECT
                    timezone,
                    locale,
                    preferred_channel,
                    to_char(quiet_hours_start, 'HH24:MI') AS quiet_hours_start,
                    to_char(quiet_hours_end, 'HH24:MI') AS quiet_hours_end,
                    brief_enabled,
                    to_char(brief_time_local, 'HH24:MI') AS brief_time_local,
                    brief_sections,
                    feature_flags
                FROM user_settings
                WHERE user_id = $1::uuid
                """,
                user_id,
            )
        except asyncpg.UndefinedTableError:
            logger.warning("user_settings table missing; using defaults")
            return UserSettings()
        except Exception:
            logger.exception("failed to load user_settings for %s", user_id)
            return UserSettings()

        if record is None:
            return UserSettings()

        return _row_to_settings(record)


def _row_to_settings(record: asyncpg.Record) -> UserSettings:
    brief_sections = default_brief_sections()
    raw_sections = record["brief_sections"]
    if raw_sections:
        if isinstance(raw_sections, str):
            brief_sections = json.loads(raw_sections)
        else:
            brief_sections = dict(raw_sections)

    feature_flags: dict[str, Any] = {}
    raw_flags = record["feature_flags"]
    if raw_flags:
        if isinstance(raw_flags, str):
            feature_flags = json.loads(raw_flags)
        else:
            feature_flags = dict(raw_flags)

    return UserSettings(
        timezone=record["timezone"] or "UTC",
        locale=record["locale"] or "en",
        preferred_channel=record["preferred_channel"] or "web",
        quiet_hours_start=record["quiet_hours_start"],
        quiet_hours_end=record["quiet_hours_end"],
        brief_enabled=bool(record["brief_enabled"]),
        brief_time_local=record["brief_time_local"] or "08:00",
        brief_sections=brief_sections,
        feature_flags=feature_flags,
    )
