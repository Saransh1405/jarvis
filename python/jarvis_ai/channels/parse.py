"""Small parsers for Telegram text and inline-button callbacks."""

import hashlib
import re

_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def hash_link_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def parse_command(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    head, _, rest = stripped.partition(" ")
    name = head.split("@", 1)[0].lower()
    if not name.startswith("/"):
        return None
    return name, rest.strip()


def parse_callback(data: str) -> tuple[str, str] | None:
    """Return ('a'|'r', action_id) for approve/reject callbacks. Anything else is ignored."""
    if len(data) < 3 or data[1] != ":":
        return None
    kind = data[0]
    action_id = data[2:]
    if kind not in ("a", "r") or _UUID.match(action_id) is None:
        return None
    return kind, action_id
