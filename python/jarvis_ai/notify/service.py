"""Pick a channel, honor quiet hours, and dedupe outbound notifications."""

import logging
from dataclasses import dataclass
from datetime import datetime

from jarvis_ai.channels.base import ChannelAdapter, OutboundMessage, UserChannel
from jarvis_ai.notify.quiet import in_quiet_hours
from jarvis_ai.user_settings.formatting import now_local_iso
from jarvis_ai.user_settings.tz import resolve_zone

logger = logging.getLogger(__name__)


@dataclass
class NotifyResult:
    status: str
    channel: str | None = None
    notification_id: str | None = None
    error: str | None = None


class NotifyService:
    def __init__(self, settings_store, notifications, adapters: dict[str, ChannelAdapter], channels) -> None:
        self._settings = settings_store
        self._notifications = notifications
        self._adapters = adapters
        self._channels = channels

    async def notify(
        self,
        user_id: str,
        kind: str,
        message: OutboundMessage,
        *,
        dedupe_key: str | None = None,
        bypass_quiet_hours: bool = False,
        ref_id: str | None = None,
    ) -> NotifyResult:
        settings = await self._settings.get(user_id)
        local_now = datetime.now(resolve_zone(settings.timezone))
        if not bypass_quiet_hours and in_quiet_hours(
            local_now, settings.quiet_hours_start, settings.quiet_hours_end
        ):
            logger.info(
                "notification skipped quiet_hours user_id=%s kind=%s now_local=%s",
                user_id,
                kind,
                now_local_iso(settings.timezone),
            )
            return NotifyResult(status="skipped")

        channel_name, user_channel = await self._resolve_channel(user_id, settings.preferred_channel)
        adapter = self._adapters.get(channel_name)
        if adapter is None:
            return NotifyResult(status="failed", channel=channel_name, error="no adapter")

        notification_id = await self._notifications.insert(
            user_id=user_id,
            kind=kind,
            channel=channel_name,
            status="queued",
            dedupe_key=dedupe_key,
            ref_id=ref_id,
        )
        if notification_id is None:
            return NotifyResult(status="deduped", channel=channel_name)

        result = await adapter.send(user_channel, message)
        if result.blocked and channel_name != "web":
            await self._channels.set_status(user_id, channel_name, "blocked")
            await self._notifications.mark(notification_id, "failed", result.error)
            return await self._fallback_web(
                user_id, kind, message, notification_error=result.error, ref_id=ref_id
            )

        if not result.ok:
            await self._notifications.mark(notification_id, "failed", result.error)
            return NotifyResult(
                status="failed",
                channel=channel_name,
                notification_id=notification_id,
                error=result.error,
            )

        await self._notifications.mark(notification_id, "sent")
        return NotifyResult(status="sent", channel=channel_name, notification_id=notification_id)

    async def _resolve_channel(
        self, user_id: str, preferred: str
    ) -> tuple[str, UserChannel | None]:
        if preferred and preferred != "web":
            row = await self._channels.get_for_user(user_id, preferred)
            if row is not None and row.status == "active":
                return preferred, row
        return "web", None

    async def _fallback_web(
        self,
        user_id: str,
        kind: str,
        message: OutboundMessage,
        *,
        notification_error: str | None,
        ref_id: str | None,
    ) -> NotifyResult:
        adapter = self._adapters.get("web")
        if adapter is None:
            return NotifyResult(status="failed", channel="web", error=notification_error)
        notification_id = await self._notifications.insert(
            user_id=user_id,
            kind=kind,
            channel="web",
            status="queued",
            dedupe_key=None,
            ref_id=ref_id,
        )
        if notification_id is None:
            return NotifyResult(status="failed", channel="web", error="fallback insert failed")
        result = await adapter.send(None, message)
        if not result.ok:
            await self._notifications.mark(notification_id, "failed", result.error)
            return NotifyResult(status="failed", channel="web", notification_id=notification_id, error=result.error)
        await self._notifications.mark(notification_id, "sent")
        return NotifyResult(status="sent", channel="web", notification_id=notification_id)
