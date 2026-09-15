package observability

import (
	"context"
	"io"
	"log/slog"
	"os"
	"strings"
)

func NewLogger(level, format string) *slog.Logger {
	opts := &slog.HandlerOptions{Level: parseLogLevel(level)}
	var handler slog.Handler
	if strings.EqualFold(format, "text") {
		handler = slog.NewTextHandler(os.Stdout, opts)
	} else {
		handler = slog.NewJSONHandler(os.Stdout, opts)
	}
	return slog.New(handler)
}

func NewLoggerWithWriter(w io.Writer, level, format string) *slog.Logger {
	opts := &slog.HandlerOptions{Level: parseLogLevel(level)}
	if strings.EqualFold(format, "text") {
		return slog.New(slog.NewTextHandler(w, opts))
	}
	return slog.New(slog.NewJSONHandler(w, opts))
}

func parseLogLevel(level string) slog.Level {
	switch strings.ToLower(level) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

func LoggerFromContext(ctx context.Context, base *slog.Logger) *slog.Logger {
	if base == nil {
		base = slog.Default()
	}
	if id := RequestIDFromContext(ctx); id != "" {
		return base.With("request_id", id)
	}
	return base
}
