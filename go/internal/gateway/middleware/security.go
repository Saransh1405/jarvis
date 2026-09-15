package middleware

import (
	"jarvis-go/internal/gateway/config"

	"github.com/gin-gonic/gin"
)

func Security(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		h := c.Writer.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "strict-origin-when-cross-origin")
		h.Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		h.Set("X-XSS-Protection", "0")
		h.Set("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")

		if c.Request.TLS != nil || c.GetHeader("X-Forwarded-Proto") == "https" {
			h.Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
		}

		c.Next()
	}
}

func ConfigureTrustedProxies(engine *gin.Engine, cfg *config.Config) error {
	if len(cfg.TrustedProxies) == 0 {
		return engine.SetTrustedProxies(nil)
	}
	return engine.SetTrustedProxies(cfg.TrustedProxies)
}
