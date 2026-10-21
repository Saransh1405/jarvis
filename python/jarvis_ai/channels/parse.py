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


# Longer prefixes first so s10/s60 are not read as a single-letter kind.
_CALLBACK_KINDS = ("s10", "s60", "st", "md", "a", "r", "d")


def parse_callback(data: str) -> tuple[str, str] | None:
    """Return (kind, id) for approve, reject, done, and snooze callbacks."""
    for kind in _CALLBACK_KINDS:
        prefix = f"{kind}:"
        if not data.startswith(prefix):
            continue
        target_id = data[len(prefix) :]
        if _UUID.match(target_id) is None:
            return None
        return kind, target_id
    return None
