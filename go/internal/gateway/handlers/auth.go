package handlers

import (
	"net/http"
	"time"

	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/response"

	"github.com/gin-gonic/gin"
)

type LoginRequest struct {
	Username string `json:"username" validate:"required"`
	Password string `json:"password" validate:"required"`
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
}

func NewAuthHandler(cfg *config.Config, validator *auth.Validator) *AuthHandler {
	return &AuthHandler{cfg: cfg, validator: validator}
}

func (h *AuthHandler) Login(c *gin.Context) {
	if !h.cfg.DevAuthEnabled {
		response.Error(c, http.StatusNotFound, "not_found", "login is disabled")
		return
	}

	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid_request", err.Error())
		return
	}

	if req.Username != h.cfg.DevAuthUsername || req.Password != h.cfg.DevAuthPassword {
		response.Unauthorized(c, "invalid credentials")
		return
	}

	ttl := h.cfg.JWTTTL
	if ttl <= 0 {
		ttl = 24 * time.Hour
	}

	token, err := h.validator.IssueToken(
		h.cfg.DevAuthUserID,
		h.cfg.DevAuthRoles,
		h.cfg.DevAuthPermissions,
		ttl,
	)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.JSON(c, http.StatusOK, LoginResponse{
		AccessToken: token,
		TokenType:   "Bearer",
		ExpiresIn:   int64(ttl.Seconds()),
		UserID:      h.cfg.DevAuthUserID,
	})
}
