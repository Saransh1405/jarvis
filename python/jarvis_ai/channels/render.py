"""Render model Markdown into the small HTML subset Telegram accepts."""

import html
import re

TELEGRAM_MAX_LEN = 4096

_FENCE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n?(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def render_telegram_html(text: str) -> str:
    """Escape text, then restore a small set of Markdown constructs as HTML."""
    if not text:
        return ""

    slots: list[str] = []

    def _hold(rendered: str) -> str:
        slots.append(rendered)
        return f"\x00{len(slots) - 1}\x00"

    def _fence(match: re.Match[str]) -> str:
        body = html.escape(match.group(1).strip("\n"))
        return _hold(f"<pre>{body}</pre>")

    def _code(match: re.Match[str]) -> str:
        return _hold(f"<code>{html.escape(match.group(1))}</code>")

    protected = _FENCE.sub(_fence, text)
    protected = _INLINE_CODE.sub(_code, protected)
    escaped = html.escape(protected)
    escaped = _LINK.sub(
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    escaped = _BOLD.sub(r"<b>\1</b>", escaped)
    escaped = _ITALIC.sub(r"<i>\1</i>", escaped)

    def _restore(match: re.Match[str]) -> str:
        return slots[int(match.group(1))]

    return re.sub(r"\x00(\d+)\x00", _restore, escaped)


def split_telegram_messages(text: str, limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    """Split on paragraph boundaries, then lines, then a hard cut."""
    if text is None:
        return [""]
    if len(text) <= limit:
        return [text] if text else [""]

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        window = remaining[:limit]
        cut = window.rfind("\n\n")
        if cut < limit // 2:
            cut = window.rfind("\n")
        if cut < limit // 2:
            cut = limit
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    return parts or [""]
