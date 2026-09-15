"""Simple routing helpers — Phase 2.3 (before LLM picks tools)."""

import re

# Matches: "calculate 2+2", "calc 99*101"
_CALC_PREFIX = re.compile(r"^(?:calculate|calc)\s+(.+)$", re.IGNORECASE)

# Matches bare math like "99*101" or "(10+5)/3"
_MATH_CHARS = re.compile(r"^[\d\s+\-*/().%]+$")


def try_extract_calculator_expression(message: str) -> str | None:
    """
    Return a math expression if this message should use the calculator tool.

    Examples that match:
      - "calculate 2+2"
      - "calc 99*101"
      - "15*0.2"   (bare expression)

    Examples that do not match:
      - "hello"
      - "what is 2+2?"  (LLM will handle in 2.4)
    """
    text = message.strip()
    if not text:
        return None

    prefix_match = _CALC_PREFIX.match(text)
    if prefix_match:
        return prefix_match.group(1).strip()

    if _MATH_CHARS.match(text) and any(op in text for op in "+-*/"):
        return text

    return None
