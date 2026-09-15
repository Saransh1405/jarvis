package middleware

import (
	"net/http"
	"strings"

	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/response"

	"github.com/gin-gonic/gin"
)

func RequestValidation(cfg *config.Config) gin.HandlerFunc {
	maxBytes := cfg.MaxRequestBodyBytes
	if maxBytes <= 0 {
		maxBytes = 1 << 20
	}

	return func(c *gin.Context) {
		c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, maxBytes)

		method := c.Request.Method
		if method != http.MethodPost && method != http.MethodPut && method != http.MethodPatch {
			c.Next()
			return
		}

		ct := strings.ToLower(strings.TrimSpace(c.GetHeader("Content-Type")))
		if ct == "" {
			response.BadRequest(c, "missing_content_type", "Content-Type header is required")
			return
		}

		if !strings.HasPrefix(ct, "application/json") {
			response.BadRequest(c, "invalid_content_type", "Content-Type must be application/json")
			return
		}

		c.Next()
	}
}

func BindAndValidate(c *gin.Context, dest any) bool {
	if err := c.ShouldBindJSON(dest); err != nil {
		response.BadRequest(c, "invalid_request", err.Error())
		return false
	}
	if err := defaultValidator.Struct(dest); err != nil {
		response.BadRequest(c, "validation_failed", err.Error())
		return false
	}
	return true
}
