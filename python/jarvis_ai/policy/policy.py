from enum import Enum

# Mirrors go/internal/policy/policy.go — keep both in sync.
# TODO: Phase 2 - implement the decision engine.
class Tier(Enum):
    SAFE = "safe"
    CONFIRM_REQUIRED = "confirm_required"
    ALWAYS_CONFIRM = "always_confirm"
