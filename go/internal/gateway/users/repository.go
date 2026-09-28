package users

import (
	"context"
	"errors"
	"fmt"

	"jarvis-go/internal/db/postgres"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// Repository is a Postgres-backed user store.
type Repository struct {
	pool *postgres.Pool
}

func NewRepository(pool *postgres.Pool) *Repository {
	return &Repository{pool: pool}
}

func (r *Repository) CreateUser(ctx context.Context, email, passwordHash string) (string, error) {
	email = NormalizeEmail(email)
	var userID string
	err := r.pool.QueryRow(ctx,
		`INSERT INTO users (email, password_hash)
		 VALUES ($1, $2)
		 RETURNING id::text`,
		email,
		passwordHash,
	).Scan(&userID)
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return "", ErrDuplicateEmail
		}
		return "", fmt.Errorf("insert user: %w", err)
	}
	return userID, nil
}

func (r *Repository) FindByEmail(ctx context.Context, email string) (string, string, error) {
	email = NormalizeEmail(email)
	var userID, passwordHash string
	err := r.pool.QueryRow(ctx,
		`SELECT id::text, password_hash FROM users WHERE lower(email) = $1`,
		email,
	).Scan(&userID, &passwordHash)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return "", "", ErrNotFound
		}
		return "", "", fmt.Errorf("find user: %w", err)
	}
	return userID, passwordHash, nil
}
