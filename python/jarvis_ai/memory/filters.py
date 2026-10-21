"""Reject secrets and sensitive categories before they are stored."""

import re

_SK = re.compile(r"sk-[A-Za-z0-9]{8,}")
_SECRET_LABEL = re.compile(
    r"\b(?:password|passcode|otp|api[_ ]?key|secret key)\b\s*[:=]?\s*\S+",
    re.IGNORECASE,
)
_LONG_HEX = re.compile(r"\b[a-fA-F0-9]{32,}\b")
_CARD = re.compile(r"\d{13,19}")
_SENSITIVE = re.compile(
    r"\b(?:diagnosed|diagnosis|cancer|depression|depressed|anxiety disorder|"
    r"salary|bank account|credit card|voted for|republican|democrat|"
    r"muslim|christian|hindu|jewish|atheist|gay|lesbian|bisexual|"
    r"sexual orientation|aadhaar|passport number)\b",
    re.IGNORECASE,
)


def is_secret(text: str) -> bool:
    if _SK.search(text) or _SECRET_LABEL.search(text) or _LONG_HEX.search(text):
        return True
    digits = re.sub(r"[ -]", "", text)
    return _CARD.search(digits) is not None


def is_sensitive(text: str) -> bool:
    return _SENSITIVE.search(text) is not None


def allow_extracted(text: str, source_turns: list[str]) -> bool:
    """Implicit extraction may store a sensitive fact only when the user said to remember it."""
    if is_secret(text):
        return False
    if not is_sensitive(text):
        return True
    blob = " ".join(source_turns).lower()
    return "remember" in blob
