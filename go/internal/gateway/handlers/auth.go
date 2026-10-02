package handlers

import (
	"errors"
	"net/http"
	"time"

	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/middleware"
	"jarvis-go/internal/gateway/response"
	"jarvis-go/internal/gateway/users"
	"jarvis-go/internal/gateway/usersettings"

	"github.com/gin-gonic/gin"
)

type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password" validate:"required"`
	Username string `json:"username"`
}

type SignupRequest struct {
	Email    string `json:"email" validate:"required,email,max=254"`
	Password string `json:"password" validate:"required,min=8,max=128"`
	Timezone string `json:"timezone"`
}

type LoginResponse struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
	ExpiresIn   int64  `json:"expires_in"`
	UserID      string `json:"user_id"`
}

type AuthHandler struct {
	cfg       *config.Config
	validator *auth.Validator
	users     users.Store
	settings  usersettings.Store
}

func NewAuthHandler(cfg *config.Config, validator *auth.Validator, userStore users.Store, settingsStore usersettings.Store) *AuthHandler {
	return &AuthHandler{cfg: cfg, validator: validator, users: userStore, settings: settingsStore}
}

func (h *AuthHandler) Signup(c *gin.Context) {
	if h.users == nil {
		response.Error(c, http.StatusServiceUnavailable, "unavailable", "signup requires database auth")
		return
	}

	var req SignupRequest
	if !middleware.BindAndValidate(c, &req) {
		return
	}

	hash, err := users.HashPassword(req.Password)
	if err != nil {
		response.InternalError(c)
		return
	}

	userID, err := h.users.CreateUser(c.Request.Context(), req.Email, hash)
	if err != nil {
		if errors.Is(err, users.ErrDuplicateEmail) {
			response.Error(c, http.StatusConflict, "email_taken", "email already registered")
			return
		}
		response.InternalError(c)
		return
	}

	if h.settings != nil {
		tz := usersettings.NormalizeTimezone(req.Timezone)
		if err := h.settings.EnsureDefaults(c.Request.Context(), userID, tz); err != nil {
			response.InternalError(c)
			return
		}
	}

	h.respondWithToken(c, userID)
}

func (h *AuthHandler) Login(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid_request", err.Error())
		return
	}
	if req.Password == "" {
		response.BadRequest(c, "invalid_request", "password is required")
		return
	}

	if h.users != nil {
		email := users.NormalizeEmail(req.Email)
		if email == "" {
			response.BadRequest(c, "invalid_request", "email is required")
			return
		}

		userID, hash, err := h.users.FindByEmail(c.Request.Context(), email)
		if err != nil {
			if errors.Is(err, users.ErrNotFound) {
				response.Unauthorized(c, "invalid credentials")
				return
			}
			response.InternalError(c)
			return
		}

		if err := users.CheckPassword(hash, req.Password); err != nil {
			response.Unauthorized(c, "invalid credentials")
			return
		}

		h.respondWithToken(c, userID)
		return
	}

	if !h.cfg.DevAuthEnabled {
		response.Error(c, http.StatusNotFound, "not_found", "login is disabled")
		return
	}

	if req.Username != h.cfg.DevAuthUsername || req.Password != h.cfg.DevAuthPassword {
		response.Unauthorized(c, "invalid credentials")
		return
	}

	h.respondWithToken(c, h.cfg.DevAuthUserID)
}

func (h *AuthHandler) respondWithToken(c *gin.Context, userID string) {
	ttl := h.cfg.JWTTTL
	if ttl <= 0 {
		ttl = 24 * time.Hour
	}

	roles := h.cfg.DevAuthRoles
	if len(roles) == 0 {
		roles = []string{"user"}
	}
	perms := h.cfg.DevAuthPermissions
	if len(perms) == 0 {
		perms = []string{"chat:read", "chat:write"}
	}

	token, err := h.validator.IssueToken(userID, roles, perms, ttl)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.JSON(c, http.StatusOK, LoginResponse{
		AccessToken: token,
		TokenType:   "Bearer",
		ExpiresIn:   int64(ttl.Seconds()),
		UserID:      userID,
	})
}
