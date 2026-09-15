package middleware

import (
	"log/slog"
	"time"

	"jarvis-go/internal/gateway/audit"
	"jarvis-go/internal/observability"

	"github.com/gin-gonic/gin"
)

func Logging(logger *slog.Logger, recorder audit.Recorder) gin.HandlerFunc {
	if logger == nil {
		logger = slog.Default()
	}
	if recorder == nil {
		recorder = audit.NopRecorder{}
	}

	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		query := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()
		ctx := c.Request.Context()
		log := observability.LoggerFromContext(ctx, logger)

		attrs := []any{
			"method", c.Request.Method,
			"path", path,
			"status", status,
			"latency_ms", latency.Milliseconds(),
			"client_ip", c.ClientIP(),
			"bytes_out", c.Writer.Size(),
		}
		if query != "" {
			attrs = append(attrs, "query", query)
		}
		userID := observability.UserIDFromContext(ctx)
		if userID != "" {
			attrs = append(attrs, "user_id", userID)
		}
		if len(c.Errors) > 0 {
			attrs = append(attrs, "errors", c.Errors.String())
		}

		switch {
		case status >= 500:
			log.Error("request completed", attrs...)
		case status >= 400:
			log.Warn("request completed", attrs...)
		default:
			log.Info("request completed", attrs...)
		}

		requestID := observability.RequestIDFromContext(ctx)
		if requestID == "" {
			if rid, ok := c.Get(RequestIDKey); ok {
				if s, ok := rid.(string); ok {
					requestID = s
				}
			}
		}

		recorder.Record(ctx, audit.Entry{
			RequestID: requestID,
			Method:    c.Request.Method,
			Path:      path,
			Status:    status,
			LatencyMs: latency.Milliseconds(),
			ClientIP:  c.ClientIP(),
			UserID:    userID,
			BytesOut:  c.Writer.Size(),
		})
	}
}
