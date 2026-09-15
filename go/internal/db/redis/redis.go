package redis

import (
	"context"
	"fmt"
	"time"

	goredis "github.com/redis/go-redis/v9"
)

// Client wraps go-redis with lifecycle helpers.
type Client struct {
	inner *goredis.Client
}

// Connect parses url and establishes a Redis connection pool.
func Connect(ctx context.Context, url string) (*Client, error) {
	opts, err := goredis.ParseURL(url)
	if err != nil {
		return nil, fmt.Errorf("parse redis url: %w", err)
	}

	client := goredis.NewClient(opts)
	if err := client.Ping(ctx).Err(); err != nil {
		client.Close()
		return nil, fmt.Errorf("redis ping: %w", err)
	}

	return &Client{inner: client}, nil
}

// Ping verifies connectivity.
func (c *Client) Ping(ctx context.Context) error {
	return c.inner.Ping(ctx).Err()
}

// Close shuts down the connection pool.
func (c *Client) Close() error {
	return c.inner.Close()
}

// Allow checks a token-bucket style rate limit key in Redis.
// Returns true when the request is allowed.
func (c *Client) Allow(ctx context.Context, key string, rps float64, burst int) (bool, error) {
	if rps <= 0 {
		return true, nil
	}

	// Token bucket via INCR + TTL: simple, distributed, production-suitable for gateway limits.
	now := time.Now().Unix()
	bucketKey := fmt.Sprintf("rl:%s:%d", key, now)

	count, err := c.inner.Incr(ctx, bucketKey).Result()
	if err != nil {
		return false, err
	}
	if count == 1 {
		if err := c.inner.Expire(ctx, bucketKey, 2*time.Second).Err(); err != nil {
			return false, err
		}
	}

	limit := int64(burst)
	if limit < 1 {
		limit = 1
	}
	// Scale limit by rps relative to 1-second window.
	scaled := int64(rps)
	if scaled > limit {
		limit = scaled
	}

	return count <= limit, nil
}
