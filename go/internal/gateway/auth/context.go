package auth

import (
	"github.com/gin-gonic/gin"
)

const (
	claimsKey = "auth_claims"
	apiKeyKey = "api_key_auth"
)

func SetClaims(c *gin.Context, claims *Claims) {
	c.Set(claimsKey, claims)
}

func ClaimsFromContext(c *gin.Context) (*Claims, bool) {
	v, ok := c.Get(claimsKey)
	if !ok {
		return nil, false
	}
	claims, ok := v.(*Claims)
	return claims, ok
}

func SetAPIKeyAuth(c *gin.Context) {
	c.Set(apiKeyKey, true)
}

func IsAPIKeyAuth(c *gin.Context) bool {
	v, ok := c.Get(apiKeyKey)
	if !ok {
		return false
	}
	b, ok := v.(bool)
	return ok && b
}
