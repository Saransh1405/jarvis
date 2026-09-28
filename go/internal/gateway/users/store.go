package users

import (
	"context"
	"errors"
)

var (
	ErrNotFound        = errors.New("user not found")
	ErrDuplicateEmail  = errors.New("email already registered")
	ErrInvalidPassword = errors.New("invalid password")
)

// Store persists user credentials for gateway authentication.
type Store interface {
	CreateUser(ctx context.Context, email, passwordHash string) (userID string, err error)
	FindByEmail(ctx context.Context, email string) (userID, passwordHash string, err error)
}
