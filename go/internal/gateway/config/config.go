package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Host         string
	Port         int
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	PythonAPIURL string
	PostgresDSN  string
	RedisURL     string
	LogLevel     string
	LogFormat    string

	JWTSecret   string
	JWTIssuer   string
	JWTAudience string
	JWTTTL      time.Duration
	APIKeys     []string

	DevAuthEnabled     bool
	DevAuthUsername    string
	DevAuthPassword    string
	DevAuthUserID      string
	DevAuthRoles       []string
	DevAuthPermissions []string

	CORSAllowedOrigins []string
	CORSAllowedMethods []string
	CORSAllowedHeaders []string
	CORSMaxAge         time.Duration

	RateLimitEnabled bool
	RateLimitRPS     float64
	RateLimitBurst   int

	MaxRequestBodyBytes int64
	TrustedProxies      []string

	TracingEnabled bool
	ServiceName    string

	PublicPaths []string

	AuditLogEnabled bool
}

func Load() (*Config, error) {
	port, err := envInt("GATEWAY_PORT", 8080)
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_PORT: %w", err)
	}

	readTimeout, err := envDuration("GATEWAY_READ_TIMEOUT", 15*time.Second)
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_READ_TIMEOUT: %w", err)
	}

	writeTimeout, err := envDuration("GATEWAY_WRITE_TIMEOUT", 5*time.Minute)
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_WRITE_TIMEOUT: %w", err)
	}

	corsMaxAge, err := envDuration("GATEWAY_CORS_MAX_AGE", 12*time.Hour)
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_CORS_MAX_AGE: %w", err)
	}

	rateLimitRPS, err := envFloat("GATEWAY_RATE_LIMIT_RPS", 10)
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_RATE_LIMIT_RPS: %w", err)
	}

	rateLimitBurst, err := envInt("GATEWAY_RATE_LIMIT_BURST", 20)
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_RATE_LIMIT_BURST: %w", err)
	}

	maxBody, err := envInt64("GATEWAY_MAX_BODY_BYTES", 1<<20) // 1 MiB
	if err != nil {
		return nil, fmt.Errorf("GATEWAY_MAX_BODY_BYTES: %w", err)
	}

	jwtTTL, err := envDuration("JWT_TTL", 24*time.Hour)
	if err != nil {
		return nil, fmt.Errorf("JWT_TTL: %w", err)
	}

	cfg := &Config{
		Host:                envString("GATEWAY_HOST", "0.0.0.0"),
		Port:                port,
		ReadTimeout:         readTimeout,
		WriteTimeout:        writeTimeout,
		PythonAPIURL:        strings.TrimRight(envString("PYTHON_API_URL", "http://localhost:8000"), "/"),
		PostgresDSN:         envString("POSTGRES_DSN", "postgres://jarvis:jarvis@localhost:5432/jarvis?sslmode=disable"),
		RedisURL:            envString("REDIS_URL", "redis://localhost:6379/0"),
		LogLevel:            envString("LOG_LEVEL", "info"),
		LogFormat:           envString("LOG_FORMAT", "json"),
		JWTSecret:           envString("JWT_SECRET", "dev-only-change-me"),
		JWTIssuer:           envString("JWT_ISSUER", "jarvis"),
		JWTAudience:         envString("JWT_AUDIENCE", "jarvis-api"),
		JWTTTL:              jwtTTL,
		APIKeys:             envCSV("GATEWAY_API_KEYS"),
		DevAuthEnabled:      envBool("GATEWAY_DEV_AUTH_ENABLED", true),
		DevAuthUsername:     envString("GATEWAY_DEV_AUTH_USERNAME", "jarvis"),
		DevAuthPassword:     envString("GATEWAY_DEV_AUTH_PASSWORD", "jarvis"),
		DevAuthUserID:       envString("GATEWAY_DEV_AUTH_USER_ID", "user-dev-1"),
		DevAuthRoles:        envCSVWithDefault("GATEWAY_DEV_AUTH_ROLES", []string{"user"}),
		DevAuthPermissions:  envCSVWithDefault("GATEWAY_DEV_AUTH_PERMISSIONS", []string{"chat:read", "chat:write"}),
		CORSAllowedOrigins:  envCSVWithDefault("GATEWAY_CORS_ORIGINS", []string{"*"}),
		CORSAllowedMethods:  envCSVWithDefault("GATEWAY_CORS_METHODS", []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}),
		CORSAllowedHeaders:  envCSVWithDefault("GATEWAY_CORS_HEADERS", []string{"Authorization", "Content-Type", "X-Request-ID", "X-API-Key"}),
		CORSMaxAge:          corsMaxAge,
		RateLimitEnabled:    envBool("GATEWAY_RATE_LIMIT_ENABLED", true),
		RateLimitRPS:        rateLimitRPS,
		RateLimitBurst:      rateLimitBurst,
		MaxRequestBodyBytes: maxBody,
		TrustedProxies:      envCSV("GATEWAY_TRUSTED_PROXIES"),
		TracingEnabled:      envBool("GATEWAY_TRACING_ENABLED", true),
		ServiceName:         envString("GATEWAY_SERVICE_NAME", "jarvis-gateway"),
		PublicPaths: envCSVWithDefault("GATEWAY_PUBLIC_PATHS", []string{
			"/health", "/ready", "/live", "/api/v1/auth/login",
		}),
		AuditLogEnabled: envBool("GATEWAY_AUDIT_LOG_ENABLED", false),
	}

	return cfg, nil
}

func (c *Config) Addr() string {
	return fmt.Sprintf("%s:%d", c.Host, c.Port)
}

func envString(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) (int, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return 0, err
	}
	return n, nil
}

func envInt64(key string, fallback int64) (int64, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return 0, err
	}
	return n, nil
}

func envFloat(key string, fallback float64) (float64, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	n, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return 0, err
	}
	return n, nil
}

func envDuration(key string, fallback time.Duration) (time.Duration, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	return time.ParseDuration(v)
}

func envBool(key string, fallback bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return fallback
	}
	return b
}

func envCSV(key string) []string {
	v := os.Getenv(key)
	if v == "" {
		return nil
	}
	return splitCSV(v)
}

func envCSVWithDefault(key string, fallback []string) []string {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	return splitCSV(v)
}

func splitCSV(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}
