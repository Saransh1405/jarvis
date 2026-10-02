package usersettings

import "context"

// Store persists per-user settings.
type Store interface {
	Get(ctx context.Context, userID string) (Settings, error)
	EnsureDefaults(ctx context.Context, userID, timezone string) error
	Update(ctx context.Context, userID string, patch Patch) (Settings, error)
}
