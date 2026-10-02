package handlers

import (
	"errors"
	"net/http"

	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/response"
	"jarvis-go/internal/gateway/usersettings"

	"github.com/gin-gonic/gin"
)

type SettingsHandler struct {
	store usersettings.Store
}

func NewSettingsHandler(store usersettings.Store) *SettingsHandler {
	return &SettingsHandler{store: store}
}

type patchSettingsRequest struct {
	Timezone         *string                         `json:"timezone"`
	Locale           *string                         `json:"locale"`
	PreferredChannel *string                         `json:"preferred_channel"`
	QuietHoursStart  *string                         `json:"quiet_hours_start"`
	QuietHoursEnd    *string                         `json:"quiet_hours_end"`
	BriefEnabled     *bool                           `json:"brief_enabled"`
	BriefTimeLocal   *string                         `json:"brief_time_local"`
	BriefSections    *usersettings.BriefSections     `json:"brief_sections"`
	FeatureFlags     *map[string]interface{}         `json:"feature_flags"`
}

func (h *SettingsHandler) Get(c *gin.Context) {
	if h.store == nil {
		response.Error(c, http.StatusServiceUnavailable, "unavailable", "settings require database")
		return
	}
	userID, ok := userIDFromClaims(c)
	if !ok {
		response.Unauthorized(c, "missing credentials")
		return
	}
	settings, err := h.store.Get(c.Request.Context(), userID)
	if err != nil {
		response.InternalError(c)
		return
	}
	response.JSON(c, http.StatusOK, settings)
}

func (h *SettingsHandler) Patch(c *gin.Context) {
	if h.store == nil {
		response.Error(c, http.StatusServiceUnavailable, "unavailable", "settings require database")
		return
	}
	userID, ok := userIDFromClaims(c)
	if !ok {
		response.Unauthorized(c, "missing credentials")
		return
	}

	var req patchSettingsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid_request", err.Error())
		return
	}

	patch := usersettings.Patch{
		Timezone:         req.Timezone,
		Locale:           req.Locale,
		PreferredChannel: req.PreferredChannel,
		BriefEnabled:     req.BriefEnabled,
		BriefTimeLocal:   req.BriefTimeLocal,
		BriefSections:    req.BriefSections,
		FeatureFlags:     req.FeatureFlags,
	}
	if req.QuietHoursStart != nil && req.QuietHoursEnd != nil {
		patch.QuietHoursStart = req.QuietHoursStart
		patch.QuietHoursEnd = req.QuietHoursEnd
	} else if req.QuietHoursStart != nil || req.QuietHoursEnd != nil {
		response.BadRequest(c, "invalid_request", "quiet_hours_start and quiet_hours_end must be sent together")
		return
	}

	settings, err := h.store.Update(c.Request.Context(), userID, patch)
	if err != nil {
		if isSettingsValidationError(err) {
			response.BadRequest(c, "invalid_request", err.Error())
			return
		}
		response.InternalError(c)
		return
	}
	response.JSON(c, http.StatusOK, settings)
}

func userIDFromClaims(c *gin.Context) (string, bool) {
	claims, ok := auth.ClaimsFromContext(c)
	if !ok || claims.UserID == "" {
		return "", false
	}
	return claims.UserID, true
}

func isSettingsValidationError(err error) bool {
	return errors.Is(err, usersettings.ErrInvalidTimezone) ||
		errors.Is(err, usersettings.ErrInvalidTime) ||
		errors.Is(err, usersettings.ErrInvalidLocale) ||
		errors.Is(err, usersettings.ErrInvalidPreferredChannel) ||
		errors.Is(err, usersettings.ErrInvalidBriefSections) ||
		errors.Is(err, usersettings.ErrQuietHoursPair)
}
