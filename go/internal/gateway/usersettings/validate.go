package usersettings

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"

	// Alpine/minimal images often have no zoneinfo; embed IANA data for LoadLocation.
	_ "time/tzdata"
)

var (
	ErrInvalidTimezone        = errors.New("invalid timezone")
	ErrInvalidTime            = errors.New("invalid time")
	ErrInvalidLocale          = errors.New("invalid locale")
	ErrInvalidPreferredChannel = errors.New("invalid preferred_channel")
	ErrInvalidBriefSections   = errors.New("invalid brief_sections")
	ErrQuietHoursPair         = errors.New("quiet_hours_start and quiet_hours_end must both be set or both cleared")
)

var (
	localePattern = regexp.MustCompile(`^[a-z]{2}(-[A-Za-z0-9]+)?$`)
	timePattern   = regexp.MustCompile(`^([01]\d|2[0-3]):[0-5]\d$`)
)

var allowedBriefSectionKeys = map[string]struct{}{
	"reminders": {},
	"calendar":  {},
	"email":     {},
	"weather":   {},
}

// timezoneAliases maps legacy or browser-reported IDs to canonical IANA names.
var timezoneAliases = map[string]string{
	"asia/calcutta": "Asia/Kolkata",
}

// CanonicalTimezone maps known aliases; otherwise returns trimmed input unchanged.
func CanonicalTimezone(tz string) string {
	tz = strings.TrimSpace(tz)
	if tz == "" {
		return ""
	}
	if canonical, ok := timezoneAliases[strings.ToLower(tz)]; ok {
		return canonical
	}
	return tz
}

// NormalizeTimezone returns a valid IANA timezone or UTC when input is empty/invalid.
func NormalizeTimezone(tz string) string {
	resolved, err := ResolveTimezone(tz)
	if err != nil {
		return "UTC"
	}
	return resolved
}

// ResolveTimezone canonicalizes and validates a timezone name.
func ResolveTimezone(tz string) (string, error) {
	tz = CanonicalTimezone(tz)
	if tz == "" {
		return "", ErrInvalidTimezone
	}
	if strings.EqualFold(tz, "local") {
		return "", ErrInvalidTimezone
	}
	if _, err := time.LoadLocation(tz); err != nil {
		return "", fmt.Errorf("%w: %s", ErrInvalidTimezone, tz)
	}
	return tz, nil
}

// ValidateTimezone rejects empty, Local, and unknown IANA names.
func ValidateTimezone(tz string) error {
	_, err := ResolveTimezone(tz)
	return err
}

// ValidateLocalTime expects HH:MM (24h).
func ValidateLocalTime(value string) error {
	if !timePattern.MatchString(strings.TrimSpace(value)) {
		return ErrInvalidTime
	}
	return nil
}

// ValidateLocale expects a short BCP-47 tag.
func ValidateLocale(locale string) error {
	locale = strings.TrimSpace(locale)
	if locale == "" || !localePattern.MatchString(locale) {
		return ErrInvalidLocale
	}
	return nil
}

// ValidatePreferredChannel accepts web or telegram.
func ValidatePreferredChannel(channel string) error {
	switch strings.TrimSpace(channel) {
	case "web", "telegram":
		return nil
	default:
		return ErrInvalidPreferredChannel
	}
}

// ValidateBriefSections ensures only known keys are present.
func ValidateBriefSections(sections BriefSections) error {
	for key := range sections {
		if _, ok := allowedBriefSectionKeys[key]; !ok {
			return fmt.Errorf("%w: unknown key %q", ErrInvalidBriefSections, key)
		}
	}
	return nil
}

// ValidatePatch validates a partial update before apply.
func ValidatePatch(patch Patch) error {
	if patch.Timezone != nil {
		if err := ValidateTimezone(*patch.Timezone); err != nil {
			return err
		}
	}
	if patch.Locale != nil {
		if err := ValidateLocale(*patch.Locale); err != nil {
			return err
		}
	}
	if patch.PreferredChannel != nil {
		if err := ValidatePreferredChannel(*patch.PreferredChannel); err != nil {
			return err
		}
	}
	if patch.BriefTimeLocal != nil {
		if err := ValidateLocalTime(*patch.BriefTimeLocal); err != nil {
			return err
		}
	}
	if patch.QuietHoursStart != nil && patch.QuietHoursEnd != nil {
		start := strings.TrimSpace(*patch.QuietHoursStart)
		end := strings.TrimSpace(*patch.QuietHoursEnd)
		if start != "" || end != "" {
			if start == "" || end == "" {
				return ErrQuietHoursPair
			}
			if err := ValidateLocalTime(start); err != nil {
				return err
			}
			if err := ValidateLocalTime(end); err != nil {
				return err
			}
		}
	}
	if patch.BriefSections != nil {
		if err := ValidateBriefSections(*patch.BriefSections); err != nil {
			return err
		}
	}

	if (patch.QuietHoursStart != nil) != (patch.QuietHoursEnd != nil) {
		return ErrQuietHoursPair
	}

	return nil
}
