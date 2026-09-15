package handlers

import (
	"context"
	"net/http"
	"time"

	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/response"

	"github.com/gin-gonic/gin"
)

type HealthHandler struct{}

func (h *HealthHandler) Live(c *gin.Context) {
	response.JSON(c, http.StatusOK, gin.H{
		"status": "ok",
		"time":   time.Now().UTC().Format(time.RFC3339),
	})
}

type ReadyHandler struct {
	Redis *redis.Client
}

func (h *ReadyHandler) Ready(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
	defer cancel()

	checks := gin.H{}
	allOK := true

	if h.Redis != nil {
		if err := h.Redis.Ping(ctx); err != nil {
			checks["redis"] = "down"
			allOK = false
		} else {
			checks["redis"] = "up"
		}
	} else {
		checks["redis"] = "skipped"
	}

	status := http.StatusOK
	statusText := "ready"
	if !allOK {
		status = http.StatusServiceUnavailable
		statusText = "not_ready"
	}

	response.JSON(c, status, gin.H{
		"status": statusText,
		"checks": checks,
	})
}
