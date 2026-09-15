package middleware

import (
	"jarvis-go/internal/observability"

	"github.com/gin-gonic/gin"
)

func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.GetHeader(RequestIDHeader)
		if id == "" {
			id = observability.NewRequestID()
		}

		c.Set(RequestIDKey, id)
		c.Header(RequestIDHeader, id)
		c.Request = c.Request.WithContext(observability.WithRequestID(c.Request.Context(), id))

		c.Next()
	}
}
