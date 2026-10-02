package usersettings

// BriefSections toggles which sections appear in the daily brief.
type BriefSections map[string]bool

// Settings is the full user_settings row exposed via the API.
type Settings struct {
	UserID            string                 `json:"user_id"`
	Timezone          string                 `json:"timezone"`
	Locale            string                 `json:"locale"`
	PreferredChannel  string                 `json:"preferred_channel"`
	QuietHoursStart   *string                `json:"quiet_hours_start"`
	QuietHoursEnd     *string                `json:"quiet_hours_end"`
	BriefEnabled      bool                   `json:"brief_enabled"`
	BriefTimeLocal    string                 `json:"brief_time_local"`
	BriefSections     BriefSections          `json:"brief_sections"`
	FeatureFlags      map[string]interface{} `json:"feature_flags"`
}

// Patch carries optional fields for partial updates.
type Patch struct {
	Timezone         *string
	Locale           *string
	PreferredChannel *string
	QuietHoursStart  *string
	QuietHoursEnd    *string
	BriefEnabled     *bool
	BriefTimeLocal   *string
	BriefSections    *BriefSections
	FeatureFlags     *map[string]interface{}
}

// DefaultBriefSections matches the SQL default.
func DefaultBriefSections() BriefSections {
	return BriefSections{
		"reminders": true,
		"calendar":  true,
		"email":     true,
		"weather":   false,
	}
}

// DefaultSettings returns API defaults for a new user.
func DefaultSettings(userID, timezone string) Settings {
	if timezone == "" {
		timezone = "UTC"
	}
	return Settings{
		UserID:           userID,
		Timezone:         timezone,
		Locale:           "en",
		PreferredChannel: "web",
		BriefEnabled:     true,
		BriefTimeLocal:   "08:00",
		BriefSections:    DefaultBriefSections(),
		FeatureFlags:     map[string]interface{}{},
	}
}
