package config

import "time"

// TestConfig returns a deterministic config for integration tests.
func TestConfig() *Config {
	return &Config{
		Host:                "127.0.0.1",
		Port:                8080,
		ReadTimeout:         5 * time.Second,
		WriteTimeout:        5 * time.Second,
		PythonAPIURL:        "http://127.0.0.1:8000",
		JWTSecret:           "test-secret-key",
		JWTIssuer:           "jarvis",
		JWTAudience:         "jarvis-api",
		JWTTTL:              time.Hour,
		PublicPaths:         []string{"/health", "/ready", "/live", "/api/v1/auth/login"},
		CORSAllowedOrigins:  []string{"*"},
		CORSAllowedMethods:  []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		CORSAllowedHeaders:  []string{"Authorization", "Content-Type", "X-Request-ID", "X-API-Key"},
		CORSMaxAge:          12 * time.Hour,
		RateLimitEnabled:    true,
		RateLimitRPS:        100,
		RateLimitBurst:      100,
		MaxRequestBodyBytes: 1 << 20,
		TracingEnabled:      false,
		ServiceName:         "jarvis-gateway-test",
		DevAuthEnabled:      true,
		DevAuthUsername:     "jarvis",
		DevAuthPassword:     "jarvis",
		DevAuthUserID:       "user-dev-1",
		DevAuthRoles:        []string{"user"},
		DevAuthPermissions:  []string{"chat:read", "chat:write"},
		AuditLogEnabled:     false,
	}
}
