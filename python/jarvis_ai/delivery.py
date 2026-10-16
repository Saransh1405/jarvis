"""Shared notifier, job queue, and brief service for the API and the worker."""

from dataclasses import dataclass

from jarvis_ai.brief.service import BriefRunsRepository, BriefService, default_sections
from jarvis_ai.channels.telegram_api import HttpxTelegramClient, TelegramAdapter
from jarvis_ai.channels.web import WebAdapter
from jarvis_ai.config.settings import Settings
from jarvis_ai.jobs.repository import JobsRepository
from jarvis_ai.llm.factory import LLMProviderError, create_llm_provider
from jarvis_ai.notify.repository import NotificationsRepository
from jarvis_ai.notify.service import NotifyService


@dataclass
class DeliveryStack:
    jobs: JobsRepository
    notifier: NotifyService
    notifications: NotificationsRepository
    briefs: BriefService
    telegram_client: HttpxTelegramClient | None
    adapters: dict


def build_delivery_stack(pool, settings: Settings, user_settings, reminders, pending) -> DeliveryStack:
    channels = _channels(pool)
    notifications = NotificationsRepository(pool)
    adapters: dict = {"web": WebAdapter()}
    telegram_client = None
    if settings.telegram_bot_token:
        telegram_client = HttpxTelegramClient(settings.telegram_bot_token)
        adapters["telegram"] = TelegramAdapter(telegram_client)
    notifier = NotifyService(user_settings, notifications, adapters, channels)
    jobs = JobsRepository(pool)
    briefs = BriefService(
        settings_store=user_settings,
        notifier=notifier,
        runs=BriefRunsRepository(pool),
        jobs=jobs,
        sections=default_sections(reminders, pending),
        llm=_optional_llm(settings),
    )
    return DeliveryStack(
        jobs=jobs,
        notifier=notifier,
        notifications=notifications,
        briefs=briefs,
        telegram_client=telegram_client,
        adapters=adapters,
    )


def _channels(pool):
    from jarvis_ai.channels.repository import ChannelsRepository

    return ChannelsRepository(pool)


def _optional_llm(settings: Settings):
    try:
        return create_llm_provider(settings)
    except LLMProviderError:
        return None
