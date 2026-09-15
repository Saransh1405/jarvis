package middleware

import (
	"strings"

	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/response"
	"jarvis-go/internal/observability"

	"github.com/gin-gonic/gin"
)

const apiKeyHeader = "X-API-Key"

func Authentication(deps Deps) gin.HandlerFunc {
	public := make(map[string]struct{}, len(deps.Config.PublicPaths))
	for _, p := range deps.Config.PublicPaths {
		public[p] = struct{}{}
	}

	apiKeys := make(map[string]struct{}, len(deps.Config.APIKeys))
	for _, k := range deps.Config.APIKeys {
		apiKeys[k] = struct{}{}
	}

	return func(c *gin.Context) {
		if _, ok := public[c.Request.URL.Path]; ok {
			c.Next()
			return
		}

		if apiKey := strings.TrimSpace(c.GetHeader(apiKeyHeader)); apiKey != "" {
			if _, ok := apiKeys[apiKey]; ok {
				auth.SetAPIKeyAuth(c)
				c.Next()
				return
			}
			response.Unauthorized(c, "invalid api key")
			return
		}

		header := c.GetHeader("Authorization")
		if header == "" {
			response.Unauthorized(c, "missing authorization")
			return
		}

		parts := strings.SplitN(header, " ", 2)
		if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
			response.Unauthorized(c, "invalid authorization header")
			return
		}

		claims, err := deps.Validator.Validate(parts[1])
		if err != nil {
			response.Unauthorized(c, "invalid or expired token")
			return
		}

		auth.SetClaims(c, claims)
		c.Request = c.Request.WithContext(observability.WithUserID(c.Request.Context(), claims.UserID))
		c.Next()
	}
}
