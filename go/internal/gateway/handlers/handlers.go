package handlers

import (
	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/proxy"
	"jarvis-go/internal/gateway/users"
	"jarvis-go/internal/gateway/usersettings"

	"log/slog"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

func RegisterRoutes(
	engine *gin.Engine,
	cfg *config.Config,
	redisClient *redis.Client,
	validator *auth.Validator,
	userStore users.Store,
	settingsStore usersettings.Store,
) {
	health := &HealthHandler{}
	ready := &ReadyHandler{Redis: redisClient}
	authHandler := NewAuthHandler(cfg, validator, userStore, settingsStore)
	settingsHandler := NewSettingsHandler(settingsStore)
	chatProxy := proxy.NewClient(cfg.PythonAPIURL)

	engine.GET("/health", health.Live)
	engine.GET("/live", health.Live)
	engine.GET("/ready", ready.Ready)

	api := engine.Group("/api/v1")
	{
		api.POST("/auth/signup", authHandler.Signup)
		api.POST("/auth/login", authHandler.Login)
		api.GET("/me/settings", settingsHandler.Get)
		api.PATCH("/me/settings", settingsHandler.Patch)

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
		api.GET("/notifications", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/notifications")
		})
		api.GET("/conversations", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/conversations")
		})
		api.GET("/conversations/:id/messages", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/conversations/"+c.Param("id")+"/messages")
		})

		api.POST("/channels/telegram/link", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/channels/telegram/link")
		})
		api.GET("/channels/telegram", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/channels/telegram")
		})
		api.DELETE("/channels/telegram", func(c *gin.Context) {
			chatProxy.Forward(c, "/api/v1/channels/telegram")
		})
	}

	telegram := &TelegramHandler{
		Secret:        cfg.TelegramWebhookSecret,
		InternalToken: cfg.InternalAPIToken,
		PythonAPIURL:  cfg.PythonAPIURL,
		Redis:         redisClient,
		HTTP:          &http.Client{Timeout: 2 * time.Minute},
		Logger:        slog.Default(),
	}
	engine.POST("/api/v1/channels/telegram/webhook", telegram.Webhook)
}
