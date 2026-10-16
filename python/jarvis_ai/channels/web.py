from jarvis_ai.channels.base import (
    ChannelCapabilities,
    OutboundMessage,
    SendResult,
    UserChannel,
)


class WebAdapter:
    """Web chat is the HTTP response. Proactive sends are the notification row itself."""

    name = "web"
    capabilities = ChannelCapabilities(
        max_len=32000,
        supports_buttons=True,
        supports_edit=False,
        supports_markdown=True,
    )

    async def send(self, user_channel: UserChannel | None, msg: OutboundMessage) -> SendResult:
        if not msg.text and not msg.buttons:
            return SendResult(ok=False, error="empty message")
        return SendResult(ok=True)
