package handlers

import (
	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/proxy"
	"jarvis-go/internal/gateway/users"

	"github.com/gin-gonic/gin"
)

func RegisterRoutes(
	engine *gin.Engine,
	cfg *config.Config,
	redisClient *redis.Client,
	validator *auth.Validator,
	userStore users.Store,
) {
	health := &HealthHandler{}
	ready := &ReadyHandler{Redis: redisClient}
	authHandler := NewAuthHandler(cfg, validator, userStore)
	chatProxy := proxy.NewClient(cfg.PythonAPIURL)

	engine.GET("/health", health.Live)
	engine.GET("/live", health.Live)
	engine.GET("/ready", ready.Ready)

	api := engine.Group("/api/v1")
	{
		api.POST("/auth/signup", authHandler.Signup)
		api.POST("/auth/login", authHandler.Login)

		api.GET("/status", func(c *gin.Context) {
			c.JSON(200, gin.H{
				"service": cfg.ServiceName,
				"status":  "ok",
			})
		})

		api.POST("/chat", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/chat")
		})
		api.POST("/chat/stream", func(c *gin.Context) {
			chatProxy.ForwardStream(c, "/api/v1/chat/stream")
		})
		api.POST("/actions/:id/approve", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/actions/"+c.Param("id")+"/approve")
		})
		api.POST("/actions/:id/reject", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/actions/"+c.Param("id")+"/reject")
		})
	}
}
