package audit

import (
	"context"
	"log/slog"
	"time"

	"jarvis-go/internal/db/postgres"
)

type Entry struct {
	RequestID string
	Method    string
	Path      string
	Status    int
	LatencyMs int64
	ClientIP  string
	UserID    string
	BytesOut  int
}

type Recorder interface {
	Record(ctx context.Context, entry Entry)
}

type PostgresRecorder struct {
	pool   *postgres.Pool
	logger *slog.Logger
}

func NewPostgresRecorder(pool *postgres.Pool, logger *slog.Logger) *PostgresRecorder {
	if logger == nil {
		logger = slog.Default()
	}
	return &PostgresRecorder{pool: pool, logger: logger}
}

func (r *PostgresRecorder) Record(ctx context.Context, entry Entry) {
	go func() {
		insertCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()

		err := r.pool.Exec(insertCtx,
			`INSERT INTO request_logs
			 (request_id, method, path, status, latency_ms, client_ip, user_id, bytes_out)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
			entry.RequestID,
			entry.Method,
			entry.Path,
			entry.Status,
			entry.LatencyMs,
			entry.ClientIP,
			nullIfEmpty(entry.UserID),
			entry.BytesOut,
		)
		if err != nil {
			r.logger.Warn("audit log insert failed",
				"error", err,
				"request_id", entry.RequestID,
				"path", entry.Path,
			)
		}
	}()
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

type NopRecorder struct{}

func (NopRecorder) Record(_ context.Context, _ Entry) {}
