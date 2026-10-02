package usersettings

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"jarvis-go/internal/db/postgres"
)

// Repository is a Postgres-backed settings store.
type Repository struct {
	pool *postgres.Pool
}

func NewRepository(pool *postgres.Pool) *Repository {
	return &Repository{pool: pool}
}

const selectSettingsSQL = `
SELECT
    user_id::text,
    timezone,
    locale,
    preferred_channel,
    to_char(quiet_hours_start, 'HH24:MI'),
    to_char(quiet_hours_end, 'HH24:MI'),
    brief_enabled,
    to_char(brief_time_local, 'HH24:MI'),
    brief_sections,
    feature_flags
FROM user_settings
WHERE user_id = $1::uuid
`

func (r *Repository) EnsureDefaults(ctx context.Context, userID, timezone string) error {
	tz := NormalizeTimezone(timezone)
	return r.pool.Exec(ctx,
		`INSERT INTO user_settings (user_id, timezone)
		 VALUES ($1::uuid, $2)
		 ON CONFLICT (user_id) DO NOTHING`,
		userID, tz,
	)
}

func (r *Repository) Get(ctx context.Context, userID string) (Settings, error) {
	if err := r.EnsureDefaults(ctx, userID, "UTC"); err != nil {
		return Settings{}, err
	}
	return r.scanOne(ctx, userID)
}

func (r *Repository) Update(ctx context.Context, userID string, patch Patch) (Settings, error) {
	if err := ValidatePatch(patch); err != nil {
		return Settings{}, err
	}
	if err := r.EnsureDefaults(ctx, userID, "UTC"); err != nil {
		return Settings{}, err
	}

	sets := make([]string, 0, 12)
	args := make([]any, 0, 12)
	argN := 1

	if patch.Timezone != nil {
		resolved, err := ResolveTimezone(*patch.Timezone)
		if err != nil {
			return Settings{}, err
		}
		sets = append(sets, fmt.Sprintf("timezone = $%d", argN))
		args = append(args, resolved)
		argN++
	}
	if patch.Locale != nil {
		sets = append(sets, fmt.Sprintf("locale = $%d", argN))
		args = append(args, *patch.Locale)
		argN++
	}
	if patch.PreferredChannel != nil {
		sets = append(sets, fmt.Sprintf("preferred_channel = $%d", argN))
		args = append(args, *patch.PreferredChannel)
		argN++
	}
	if patch.QuietHoursStart != nil && patch.QuietHoursEnd != nil {
		start := strings.TrimSpace(*patch.QuietHoursStart)
		end := strings.TrimSpace(*patch.QuietHoursEnd)
		if start == "" && end == "" {
			sets = append(sets, "quiet_hours_start = NULL", "quiet_hours_end = NULL")
		} else {
			sets = append(sets, fmt.Sprintf("quiet_hours_start = $%d::time", argN))
			args = append(args, start)
			argN++
			sets = append(sets, fmt.Sprintf("quiet_hours_end = $%d::time", argN))
			args = append(args, end)
			argN++
		}
	}
	if patch.BriefEnabled != nil {
		sets = append(sets, fmt.Sprintf("brief_enabled = $%d", argN))
		args = append(args, *patch.BriefEnabled)
		argN++
	}
	if patch.BriefTimeLocal != nil {
		sets = append(sets, fmt.Sprintf("brief_time_local = $%d::time", argN))
		args = append(args, *patch.BriefTimeLocal)
		argN++
	}
	if patch.BriefSections != nil {
		raw, err := json.Marshal(*patch.BriefSections)
		if err != nil {
			return Settings{}, err
		}
		sets = append(sets, fmt.Sprintf("brief_sections = $%d::jsonb", argN))
		args = append(args, raw)
		argN++
	}
	if patch.FeatureFlags != nil {
		raw, err := json.Marshal(*patch.FeatureFlags)
		if err != nil {
			return Settings{}, err
		}
		sets = append(sets, fmt.Sprintf("feature_flags = $%d::jsonb", argN))
		args = append(args, raw)
		argN++
	}

	if len(sets) == 0 {
		return r.scanOne(ctx, userID)
	}

	sets = append(sets, "updated_at = NOW()")
	args = append(args, userID)
	sql := fmt.Sprintf(
		"UPDATE user_settings SET %s WHERE user_id = $%d::uuid",
		strings.Join(sets, ", "),
		argN,
	)
	if err := r.pool.Exec(ctx, sql, args...); err != nil {
		return Settings{}, fmt.Errorf("update user_settings: %w", err)
	}
	return r.scanOne(ctx, userID)
}

func (r *Repository) scanOne(ctx context.Context, userID string) (Settings, error) {
	var (
		s             Settings
		qStart, qEnd  *string
		briefSections []byte
		featureFlags  []byte
	)
	err := r.pool.QueryRow(ctx, selectSettingsSQL, userID).Scan(
		&s.UserID,
		&s.Timezone,
		&s.Locale,
		&s.PreferredChannel,
		&qStart,
		&qEnd,
		&s.BriefEnabled,
		&s.BriefTimeLocal,
		&briefSections,
		&featureFlags,
	)
	if err != nil {
		return Settings{}, fmt.Errorf("select user_settings: %w", err)
	}
	s.QuietHoursStart = qStart
	s.QuietHoursEnd = qEnd
	if len(briefSections) > 0 {
		if err := json.Unmarshal(briefSections, &s.BriefSections); err != nil {
			return Settings{}, err
		}
	} else {
		s.BriefSections = DefaultBriefSections()
	}
	if len(featureFlags) > 0 {
		if err := json.Unmarshal(featureFlags, &s.FeatureFlags); err != nil {
			return Settings{}, err
		}
	} else {
		s.FeatureFlags = map[string]interface{}{}
	}
	return s, nil
}
