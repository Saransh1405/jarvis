package middleware

import (
	"jarvis-go/internal/gateway/config"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

func Tracing(cfg *config.Config) gin.HandlerFunc {
	if cfg == nil || !cfg.TracingEnabled {
		return func(c *gin.Context) { c.Next() }
	}

	tracer := otel.Tracer(cfg.ServiceName)
	propagator := otel.GetTextMapPropagator()

	return func(c *gin.Context) {
		ctx := propagator.Extract(c.Request.Context(), propagation.HeaderCarrier(c.Request.Header))
		ctx, span := tracer.Start(ctx, c.FullPath(),
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				semconv.HTTPMethodKey.String(c.Request.Method),
				semconv.HTTPRouteKey.String(c.FullPath()),
				semconv.URLPath(c.Request.URL.Path),
			),
		)
		defer span.End()

		c.Request = c.Request.WithContext(ctx)

		if rid, ok := c.Get(RequestIDKey); ok {
			if id, ok := rid.(string); ok && id != "" {
				span.SetAttributes(attribute.String("request.id", id))
			}
		}

		c.Next()

		status := c.Writer.Status()
		span.SetAttributes(semconv.HTTPStatusCode(status))
		if len(c.Errors) > 0 {
			span.RecordError(c.Errors.Last())
			span.SetStatus(codes.Error, c.Errors.Last().Error())
		} else if status >= 500 {
			span.SetStatus(codes.Error, "server error")
		} else {
			span.SetStatus(codes.Ok, "")
		}
	}
}
