package users

import "strings"

// NormalizeEmail lowercases and trims email for storage and lookup.
func NormalizeEmail(email string) string {
	return strings.ToLower(strings.TrimSpace(email))
}
