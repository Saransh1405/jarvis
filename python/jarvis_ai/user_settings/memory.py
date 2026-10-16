from jarvis_ai.user_settings.models import UserSettings


class InMemoryUserSettingsStore:
    def __init__(self) -> None:
        self._by_user: dict[str, UserSettings] = {}

    async def get(self, user_id: str) -> UserSettings:
        if user_id not in self._by_user:
            self._by_user[user_id] = UserSettings()
        return self._by_user[user_id]

    async def update_timezone(self, user_id: str, timezone: str) -> None:
        current = await self.get(user_id)
        current.timezone = timezone

    async def set_preferred_channel(self, user_id: str, channel: str) -> None:
        current = await self.get(user_id)
        current.preferred_channel = channel

    async def list_brief_enabled(self) -> list[tuple[str, UserSettings]]:
        return [
            (user_id, settings)
            for user_id, settings in self._by_user.items()
            if settings.brief_enabled
        ]
