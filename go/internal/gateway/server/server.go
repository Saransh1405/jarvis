package server

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/audit"
	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/handlers"
	"jarvis-go/internal/gateway/middleware"
	"jarvis-go/internal/observability"

	"github.com/gin-gonic/gin"
)

// Server is the HTTP gateway server.
type Server struct {
	cfg    *config.Config
	engine *gin.Engine
	http   *http.Server
	logger *slog.Logger
}

// Options configures optional server dependencies.
type Options struct {
	AuditRecorder audit.Recorder
}

// New builds a configured Gin engine and HTTP server.
func New(cfg *config.Config, logger *slog.Logger, redisClient *redis.Client, opts Options) (*Server, error) {
	if logger == nil {
		logger = slog.Default()
	}

	gin.SetMode(gin.ReleaseMode)
	engine := gin.New()
	engine.Use(gin.Recovery())

	if err := middleware.ConfigureTrustedProxies(engine, cfg); err != nil {
		return nil, fmt.Errorf("trusted proxies: %w", err)
	}

	validator := auth.NewValidator(cfg.JWTSecret, cfg.JWTIssuer, cfg.JWTAudience)
	auditRecorder := opts.AuditRecorder
	if auditRecorder == nil {
		auditRecorder = audit.NopRecorder{}
	}

	deps := middleware.Deps{
		Logger:    logger,
		Redis:     redisClient,
		Validator: validator,
		Config:    cfg,
		Audit:     auditRecorder,
	}
	engine.Use(middleware.Chain(deps)...)

	handlers.RegisterRoutes(engine, cfg, redisClient, validator)

	srv := &http.Server{
		Addr:         cfg.Addr(),
		Handler:      engine,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	return &Server{
		cfg:    cfg,
		engine: engine,
		http:   srv,
		logger: logger,
	}, nil
}

// Handler returns the HTTP handler (for httptest and integration tests).
func (s *Server) Handler() http.Handler {
	return s.engine
}

// Run starts the HTTP server and blocks until ctx is cancelled or the server errors.
func (s *Server) Run(ctx context.Context) error {
	errCh := make(chan error, 1)
	go func() {
		s.logger.Info("gateway listening", "addr", s.cfg.Addr())
		if err := s.http.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- err
		}
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		s.logger.Info("gateway shutting down")
		return s.http.Shutdown(shutdownCtx)
	case err := <-errCh:
		return err
	}
}

// InitObservability configures logging and tracing for the gateway process.
func InitObservability(ctx context.Context, cfg *config.Config) (*slog.Logger, func(context.Context) error, error) {
	logger := observability.NewLogger(cfg.LogLevel, cfg.LogFormat)
	shutdown, err := observability.InitTracing(ctx, observability.TracingConfig{
		Enabled:     cfg.TracingEnabled,
		ServiceName: cfg.ServiceName,
	})
	if err != nil {
		return nil, nil, err
	}
	return logger, shutdown, nil
}
