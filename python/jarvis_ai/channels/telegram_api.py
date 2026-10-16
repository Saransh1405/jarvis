"""Telegram Bot API client and the outbound adapter."""

import asyncio
import logging
from typing import Any

import httpx

from jarvis_ai.channels.base import (
    ChannelCapabilities,
    OutboundMessage,
    SendResult,
    UserChannel,
)
from jarvis_ai.channels.render import render_telegram_html, split_telegram_messages

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    def __init__(self, status_code: int, description: str, retry_after: float | None = None) -> None:
        super().__init__(description)
        self.status_code = status_code
        self.description = description
        self.retry_after = retry_after


class HttpxTelegramClient:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self._client = client or httpx.AsyncClient(timeout=20)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(f"{self._base}/{method}", json=payload)
        data: dict[str, Any]
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code == 429 or data.get("ok") is False and data.get("error_code") == 429:
            retry_after = None
            params = data.get("parameters") or {}
            if isinstance(params, dict) and params.get("retry_after") is not None:
                retry_after = float(params["retry_after"])
            raise TelegramAPIError(429, str(data.get("description") or "rate limited"), retry_after)
        if response.status_code >= 400 or data.get("ok") is False:
            code = int(data.get("error_code") or response.status_code)
            raise TelegramAPIError(code, str(data.get("description") or response.text))
        result = data.get("result")
        return result if isinstance(result, dict) else {"result": result}


def _send_result_from_error(exc: TelegramAPIError) -> SendResult:
    description = exc.description.lower()
    blocked = exc.status_code == 403 and "blocked" in description
    return SendResult(
        ok=False,
        blocked=blocked,
        retry_after=exc.retry_after,
        error=exc.description,
    )


class TelegramAdapter:
    name = "telegram"
    capabilities = ChannelCapabilities(
        max_len=4096,
        supports_buttons=True,
        supports_edit=True,
        supports_markdown=False,
    )

    def __init__(self, client: HttpxTelegramClient) -> None:
        self._client = client

    async def send(self, user_channel: UserChannel | None, msg: OutboundMessage) -> SendResult:
        if user_channel is None:
            return SendResult(ok=False, error="telegram channel missing")
        text = msg.text or ""
        if msg.format == "rich":
            rendered = render_telegram_html(text)
            parse_mode = "HTML"
        else:
            rendered = text
            parse_mode = None
        chunks = split_telegram_messages(rendered)
        last_id: int | None = None
        for index, chunk in enumerate(chunks):
            payload: dict[str, Any] = {
                "chat_id": user_channel.external_id,
                "text": chunk or " ",
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if index == len(chunks) - 1 and msg.buttons:
                payload["reply_markup"] = {"inline_keyboard": _keyboard(msg)}
            result = await self._post("sendMessage", payload)
            if not result.ok:
                return result
            last_id = result.message_id
        return SendResult(ok=True, message_id=last_id)

    async def edit_message(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        *,
        rich: bool = True,
    ) -> SendResult:
        rendered = render_telegram_html(text) if rich else text
        chunks = split_telegram_messages(rendered)
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": chunks[0],
            "reply_markup": {"inline_keyboard": []},
        }
        if rich:
            payload["parse_mode"] = "HTML"
        return await self._post("editMessageText", payload)

    async def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:180]
        await self._post("answerCallbackQuery", payload)

    async def send_typing(self, chat_id: str) -> None:
        await self._post("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    async def _post(self, method: str, payload: dict[str, Any]) -> SendResult:
        try:
            result = await self._client.call(method, payload)
        except TelegramAPIError as exc:
            if exc.status_code == 429 and exc.retry_after:
                await asyncio.sleep(min(exc.retry_after, 30))
                try:
                    result = await self._client.call(method, payload)
                except TelegramAPIError as retry_exc:
                    return _send_result_from_error(retry_exc)
            else:
                logger.info("telegram %s failed status=%s", method, exc.status_code)
                return _send_result_from_error(exc)
        message_id = result.get("message_id")
        return SendResult(ok=True, message_id=int(message_id) if isinstance(message_id, int) else None)


def _keyboard(msg: OutboundMessage) -> list[list[dict[str, str]]]:
    rows: list[list[dict[str, str]]] = []
    for row in msg.buttons or []:
        rows.append(
            [{"text": button.text, "callback_data": button.callback_data[:64]} for button in row]
        )
    return rows
