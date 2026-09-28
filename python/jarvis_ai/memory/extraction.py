"""Extract durable facts from a chat turn (rules first; LLM optional later)."""

import re

from jarvis_ai.memory.helpers import MAX_FACT_LENGTH, MAX_FACTS_PER_TURN

_REMEMBER_PREFIX = re.compile(
    r"^remember(?:\s+that|\s*:|\s+for\s+me)?\s+(.+)$",
    re.IGNORECASE,
)
_MY_FACT = re.compile(
    r"^my\s+.+\s+is\s+.+",
    re.IGNORECASE,
)


def extract_chat_facts(user_message: str, assistant_message: str = "") -> list[str]:
    """
    Rule-based extraction for tests and stub LLM paths.
    Returns up to MAX_FACTS_PER_TURN normalized fact strings.
    """
    _ = assistant_message
    text = user_message.strip()
    if not text or text.endswith("?"):
        return []

    facts: list[str] = []

    match = _REMEMBER_PREFIX.match(text)
    if match:
        facts.append(match.group(1).strip()[:MAX_FACT_LENGTH])

    if _MY_FACT.match(text) and len(text) >= 15:
        if text not in facts:
            facts.append(text[:MAX_FACT_LENGTH])

    # Contact-style statements: "plumber ... number ..."
    lower = text.lower()
    if "number" in lower and any(k in lower for k in ("plumber", "phone", "contact")):
        if text not in facts:
            facts.append(text[:MAX_FACT_LENGTH])

    return facts[:MAX_FACTS_PER_TURN]
