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

	var auditRecorder audit.Recorder = audit.NopRecorder{}
	if cfg.AuditLogEnabled {
		pgPool, err := postgres.Connect(ctx, cfg.PostgresDSN)
		if err != nil {
			logger.Error("audit log enabled but postgres unavailable", "error", err)
			os.Exit(1)
		}
		defer pgPool.Close()
		auditRecorder = audit.NewPostgresRecorder(pgPool, logger)
		logger.Info("request audit logging enabled")
	}

	srv, err := server.New(cfg, logger, redisClient, server.Options{AuditRecorder: auditRecorder})
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
