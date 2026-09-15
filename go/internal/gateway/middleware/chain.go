package middleware

import (
	"log/slog"

	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/audit"
	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"

	"github.com/gin-gonic/gin"
)

type Deps struct {
	Logger    *slog.Logger
	Redis     *redis.Client
	Validator *auth.Validator
	Config    *config.Config
	Audit     audit.Recorder
}

func Chain(deps Deps) []gin.HandlerFunc {
	if deps.Audit == nil {
		deps.Audit = audit.NopRecorder{}
	}
	return []gin.HandlerFunc{
		RequestID(),
		Logging(deps.Logger, deps.Audit),
		CORS(deps.Config),
		RateLimit(deps),
		Authentication(deps),
		Authorization(deps.Config),
		RequestValidation(deps.Config),
		Security(deps.Config),
		Tracing(deps.Config),
	}
}

const RequestIDKey = "request_id"
const RequestIDHeader = "X-Request-ID"
