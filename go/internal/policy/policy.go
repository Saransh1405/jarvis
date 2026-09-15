package policy

// Tier represents a permission level for an action.
// TODO: Phase 2 - implement the decision engine.
type Tier int

const (
	Safe Tier = iota
	ConfirmRequired
	AlwaysConfirm
)
