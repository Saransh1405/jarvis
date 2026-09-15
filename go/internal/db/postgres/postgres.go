package postgres

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Pool wraps a pgx connection pool.
type Pool struct {
	pool *pgxpool.Pool
}

// Connect creates a Postgres connection pool and verifies connectivity.
func Connect(ctx context.Context, dsn string) (*Pool, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse postgres dsn: %w", err)
	}
	cfg.MaxConns = 10
	cfg.MinConns = 1
	cfg.MaxConnIdleTime = 5 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("create postgres pool: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("postgres ping: %w", err)
	}

	return &Pool{pool: pool}, nil
}

// Ping verifies database connectivity.
func (p *Pool) Ping(ctx context.Context) error {
	return p.pool.Ping(ctx)
}

// Close shuts down the pool.
func (p *Pool) Close() {
	p.pool.Close()
}

// Exec runs a SQL statement.
func (p *Pool) Exec(ctx context.Context, sql string, args ...any) error {
	_, err := p.pool.Exec(ctx, sql, args...)
	return err
}
