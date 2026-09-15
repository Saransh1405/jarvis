package middleware

import (
	"jarvis-go/internal/gateway/config"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

func CORS(cfg *config.Config) gin.HandlerFunc {
	corsCfg := cors.Config{
		AllowOrigins:     cfg.CORSAllowedOrigins,
		AllowMethods:     cfg.CORSAllowedMethods,
		AllowHeaders:     cfg.CORSAllowedHeaders,
		ExposeHeaders:    []string{RequestIDHeader, "X-Trace-ID"},
		AllowCredentials: !allowsAllOrigins(cfg.CORSAllowedOrigins),
		MaxAge:           cfg.CORSMaxAge,
	}

	return cors.New(corsCfg)
}

func allowsAllOrigins(origins []string) bool {
	for _, o := range origins {
		if o == "*" {
			return true
		}
	}
	return false
}
