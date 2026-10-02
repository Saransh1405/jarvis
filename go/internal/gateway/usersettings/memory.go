package usersettings

import (
	"context"
	"sync"
)

// MemoryStore is an in-memory settings store for tests.
type MemoryStore struct {
	mu   sync.Mutex
	byID map[string]Settings
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{byID: make(map[string]Settings)}
}

func (m *MemoryStore) EnsureDefaults(ctx context.Context, userID, timezone string) error {
	_ = ctx
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.byID[userID]; ok {
		return nil
	}
	m.byID[userID] = DefaultSettings(userID, NormalizeTimezone(timezone))
	return nil
}

func (m *MemoryStore) Get(ctx context.Context, userID string) (Settings, error) {
	_ = ctx
	if err := m.EnsureDefaults(ctx, userID, "UTC"); err != nil {
		return Settings{}, err
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.byID[userID], nil
}

func (m *MemoryStore) Update(ctx context.Context, userID string, patch Patch) (Settings, error) {
	if err := ValidatePatch(patch); err != nil {
		return Settings{}, err
	}
	if err := m.EnsureDefaults(ctx, userID, "UTC"); err != nil {
		return Settings{}, err
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	s := m.byID[userID]
	if patch.Timezone != nil {
		s.Timezone = NormalizeTimezone(*patch.Timezone)
	}
	if patch.Locale != nil {
		s.Locale = *patch.Locale
	}
	if patch.PreferredChannel != nil {
		s.PreferredChannel = *patch.PreferredChannel
	}
	if patch.QuietHoursStart != nil && patch.QuietHoursEnd != nil {
		start := *patch.QuietHoursStart
		end := *patch.QuietHoursEnd
		if start == "" && end == "" {
			s.QuietHoursStart = nil
			s.QuietHoursEnd = nil
		} else {
			s.QuietHoursStart = patch.QuietHoursStart
			s.QuietHoursEnd = patch.QuietHoursEnd
		}
	}
	if patch.BriefEnabled != nil {
		s.BriefEnabled = *patch.BriefEnabled
	}
	if patch.BriefTimeLocal != nil {
		s.BriefTimeLocal = *patch.BriefTimeLocal
	}
	if patch.BriefSections != nil {
		s.BriefSections = *patch.BriefSections
	}
	if patch.FeatureFlags != nil {
		s.FeatureFlags = *patch.FeatureFlags
	}
	m.byID[userID] = s
	return s, nil
}
