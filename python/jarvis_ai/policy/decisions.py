"""Policy outcomes for tool execution."""

from enum import Enum


class PolicyDecision(Enum):
    """Whether a tool may run for the current user/context."""

    ALLOW = "allow"
    NEEDS_CONFIRM = "needs_confirm"
    DENY = "deny"
