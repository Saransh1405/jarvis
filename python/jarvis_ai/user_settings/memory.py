from jarvis_ai.user_settings.models import UserSettings


class InMemoryUserSettingsStore:
    def __init__(self) -> None:
        self._by_user: dict[str, UserSettings] = {}

    async def get(self, user_id: str) -> UserSettings:
        if user_id not in self._by_user:
            self._by_user[user_id] = UserSettings()
        return self._by_user[user_id]
