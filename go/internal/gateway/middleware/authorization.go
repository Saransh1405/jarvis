package middleware

import (
	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/response"

	"github.com/gin-gonic/gin"
)

type PermissionRequirement struct {
	Role       string
	Permission string
	AnyOfRoles []string
	AnyOfPerms []string
}

var routeRequirements = map[string]PermissionRequirement{
	"/api/v1/admin": {Role: "admin"},
}

func Authorization(cfg *config.Config) gin.HandlerFunc {
	public := make(map[string]struct{}, len(cfg.PublicPaths))
	for _, p := range cfg.PublicPaths {
		public[p] = struct{}{}
	}

	return func(c *gin.Context) {
		if _, ok := public[c.Request.URL.Path]; ok {
			c.Next()
			return
		}

		if auth.IsAPIKeyAuth(c) {
			c.Next()
			return
		}

		req, ok := routeRequirements[c.Request.URL.Path]
		if !ok {
			c.Next()
			return
		}

		claims, ok := auth.ClaimsFromContext(c)
		if !ok {
			response.Forbidden(c, "missing credentials")
			return
		}

		if req.Role != "" && !auth.HasRole(claims, req.Role) {
			response.Forbidden(c, "insufficient role")
			return
		}
		if req.Permission != "" && !auth.HasPermission(claims, req.Permission) {
			response.Forbidden(c, "insufficient permission")
			return
		}
		for _, role := range req.AnyOfRoles {
			if auth.HasRole(claims, role) {
				c.Next()
				return
			}
		}
		for _, perm := range req.AnyOfPerms {
			if auth.HasPermission(claims, perm) {
				c.Next()
				return
			}
		}
		if len(req.AnyOfRoles) > 0 || len(req.AnyOfPerms) > 0 {
			response.Forbidden(c, "insufficient privileges")
			return
		}

		c.Next()
	}
}

func RequirePermission(permission string) gin.HandlerFunc {
	return func(c *gin.Context) {
		claims, ok := auth.ClaimsFromContext(c)
		if !ok || !auth.HasPermission(claims, permission) {
			response.Forbidden(c, "insufficient permission")
			return
		}
		c.Next()
	}
}

func RequireRole(role string) gin.HandlerFunc {
	return func(c *gin.Context) {
		claims, ok := auth.ClaimsFromContext(c)
		if !ok || !auth.HasRole(claims, role) {
			response.Forbidden(c, "insufficient role")
			return
		}
		c.Next()
	}
}
