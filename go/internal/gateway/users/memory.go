package users

import (
	"context"
	"strconv"
	"sync"
)

// MemoryStore is an in-memory user store for tests.
type MemoryStore struct {
	mu    sync.Mutex
	byEmail map[string]struct {
		id   string
		hash string
	}
	nextID int
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		byEmail: make(map[string]struct {
			id   string
			hash string
		}),
	}
}

func (m *MemoryStore) CreateUser(ctx context.Context, email, passwordHash string) (string, error) {
	_ = ctx
	email = NormalizeEmail(email)
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.byEmail[email]; ok {
		return "", ErrDuplicateEmail
	}
	m.nextID++
	userID := "user-test-" + strconv.Itoa(m.nextID)
	m.byEmail[email] = struct {
		id   string
		hash string
	}{id: userID, hash: passwordHash}
	return userID, nil
}

func (m *MemoryStore) FindByEmail(ctx context.Context, email string) (string, string, error) {
	_ = ctx
	email = NormalizeEmail(email)
	m.mu.Lock()
	defer m.mu.Unlock()
	u, ok := m.byEmail[email]
	if !ok {
		return "", "", ErrNotFound
	}
	return u.id, u.hash, nil
}
