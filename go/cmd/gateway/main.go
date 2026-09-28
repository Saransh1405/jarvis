package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"jarvis-go/internal/db/postgres"
	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/audit"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/server"
	"jarvis-go/internal/gateway/users"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		panic(err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	logger, traceShutdown, err := server.InitObservability(ctx, cfg)
	if err != nil {
		panic(err)
	}
	defer func() {
		if err := traceShutdown(context.Background()); err != nil {
			logger.Error("trace shutdown failed", "error", err)
		}
	}()

	redisClient, err := redis.Connect(ctx, cfg.RedisURL)
	if err != nil {
		logger.Warn("redis unavailable, using in-memory rate limiting", "error", err)
		redisClient = nil
	}
	if redisClient != nil {
		defer func() {
			if err := redisClient.Close(); err != nil {
				logger.Error("redis close failed", "error", err)
			}
		}()
	}

	var userStore users.Store
	var auditRecorder audit.Recorder = audit.NopRecorder{}

	if cfg.PostgresDSN != "" {
		pgPool, err := postgres.Connect(ctx, cfg.PostgresDSN)
		if err != nil {
			if cfg.AuthRequiresDB {
				logger.Error("postgres required for auth but unavailable", "error", err)
				os.Exit(1)
			}
			logger.Warn("postgres unavailable, dev auth only", "error", err)
		} else {
			defer pgPool.Close()
			userStore = users.NewRepository(pgPool)
			logger.Info("database auth enabled")
			if cfg.AuditLogEnabled {
				auditRecorder = audit.NewPostgresRecorder(pgPool, logger)
				logger.Info("request audit logging enabled")
			}
		}
	} else if cfg.AuthRequiresDB {
		logger.Error("GATEWAY_AUTH_REQUIRES_DB is true but POSTGRES_DSN is empty")
		os.Exit(1)
	}

	srv, err := server.New(cfg, logger, redisClient, server.Options{
		AuditRecorder: auditRecorder,
		Users:         userStore,
	})
	if err != nil {
		logger.Error("server init failed", "error", err)
		os.Exit(1)
	}

	if err := srv.Run(ctx); err != nil {
		logger.Error("server stopped with error", "error", err)
		os.Exit(1)
	}
	logger.Info("gateway stopped")
}
