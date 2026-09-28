"""Policy engine — decides if a tool may run before execution."""

from jarvis_ai.policy.decisions import PolicyDecision
from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool


class PolicyEngine:
    """
    Evaluates tool tier against policy rules.

    Tier semantics (mirrors go/internal/policy/policy.go):
    - SAFE: run immediately
    - CONFIRM_REQUIRED / ALWAYS_CONFIRM: block until user approves (Phase 2.7)
    - unknown tool: deny
    - confirm-tier tools require a user_id (no anonymous writes)
    """

    def evaluate(
        self,
        tool: Tool | None,
        tool_name: str,
        user_id: str | None = None,
    ) -> PolicyDecision:
        if tool is None:
            return PolicyDecision.DENY

        if tool.tier == Tier.SAFE:
            return PolicyDecision.ALLOW

        if tool.tier in (Tier.CONFIRM_REQUIRED, Tier.ALWAYS_CONFIRM):
            if not user_id:
                return PolicyDecision.DENY
            return PolicyDecision.NEEDS_CONFIRM

        return PolicyDecision.DENY
