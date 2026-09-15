package server_test

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"jarvis-go/internal/gateway/auth"
	"jarvis-go/internal/gateway/config"
	"jarvis-go/internal/gateway/middleware"
	"jarvis-go/internal/gateway/server"
	"jarvis-go/internal/observability"
)

func TestMain(m *testing.M) {
	m.Run()
}

func newTestServer(t *testing.T, cfg *config.Config) *httptest.Server {
	t.Helper()
	logger := observability.NewLoggerWithWriter(io.Discard, "error", "json")
	srv, err := server.New(cfg, logger, nil, server.Options{})
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return httptest.NewServer(srv.Handler())
}

func issueTestToken(cfg *config.Config) string {
	v := auth.NewValidator(cfg.JWTSecret, cfg.JWTIssuer, cfg.JWTAudience)
	token, err := v.IssueToken("test-user", []string{"user"}, []string{"chat:write"}, time.Hour)
	if err != nil {
		panic(err)
	}
	return token
}

func TestPublicRoutesSkipAuth(t *testing.T) {
	cfg := config.TestConfig()
	ts := newTestServer(t, cfg)
	defer ts.Close()

	paths := []string{"/health", "/live", "/ready"}
	for _, path := range paths {
		t.Run(path, func(t *testing.T) {
			resp, err := http.Get(ts.URL + path)
			if err != nil {
				t.Fatalf("GET %s: %v", path, err)
			}
			defer resp.Body.Close()

			if resp.StatusCode == http.StatusUnauthorized {
				t.Fatalf("GET %s returned 401 — public route should skip auth", path)
			}
			if resp.StatusCode >= 500 {
				t.Fatalf("GET %s returned %d", path, resp.StatusCode)
			}
		})
	}
}

func TestProtectedRoutesReturn401(t *testing.T) {
	cfg := config.TestConfig()
	ts := newTestServer(t, cfg)
	defer ts.Close()

	t.Run("missing authorization", func(t *testing.T) {
		resp, err := http.Get(ts.URL + "/api/v1/status")
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("expected 401, got %d", resp.StatusCode)
		}
		body, _ := io.ReadAll(resp.Body)
		if !strings.Contains(string(body), "unauthorized") {
			t.Fatalf("expected unauthorized error body, got %s", body)
		}
	})

	t.Run("invalid bearer token", func(t *testing.T) {
		req, err := http.NewRequest(http.MethodGet, ts.URL+"/api/v1/status", nil)
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Authorization", "Bearer not-a-real-token")
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("expected 401, got %d", resp.StatusCode)
		}
	})

	t.Run("valid bearer token", func(t *testing.T) {
		token := issueTestToken(cfg)
		req, err := http.NewRequest(http.MethodGet, ts.URL+"/api/v1/status", nil)
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Authorization", "Bearer "+token)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			t.Fatalf("expected 200, got %d body=%s", resp.StatusCode, body)
		}
	})
}

func TestRateLimitReturns429(t *testing.T) {
	cfg := config.TestConfig()
	cfg.RateLimitEnabled = true
	cfg.RateLimitRPS = 1
	cfg.RateLimitBurst = 1

	ts := newTestServer(t, cfg)
	defer ts.Close()

	client := ts.Client()
	url := ts.URL + "/health"

	// First request should succeed.
	resp1, err := client.Get(url)
	if err != nil {
		t.Fatal(err)
	}
	resp1.Body.Close()
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("first request: expected 200, got %d", resp1.StatusCode)
	}

	// Second immediate request should be rate limited.
	resp2, err := client.Get(url)
	if err != nil {
		t.Fatal(err)
	}
	defer resp2.Body.Close()

	if resp2.StatusCode != http.StatusTooManyRequests {
		body, _ := io.ReadAll(resp2.Body)
		t.Fatalf("expected 429, got %d body=%s", resp2.StatusCode, body)
	}

	body, _ := io.ReadAll(resp2.Body)
	if !strings.Contains(string(body), "rate_limit_exceeded") {
		t.Fatalf("expected rate_limit_exceeded in body, got %s", body)
	}
}

func TestRateLimitDisabledAllowsBurst(t *testing.T) {
	cfg := config.TestConfig()
	cfg.RateLimitEnabled = false
	cfg.RateLimitRPS = 1
	cfg.RateLimitBurst = 1

	ts := newTestServer(t, cfg)
	defer ts.Close()

	for i := 0; i < 5; i++ {
		resp, err := http.Get(ts.URL + "/health")
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode == http.StatusTooManyRequests {
			t.Fatalf("request %d was rate limited but RateLimitEnabled=false", i+1)
		}
	}
}

func TestRequestIDHeaderIsSet(t *testing.T) {
	cfg := config.TestConfig()
	ts := newTestServer(t, cfg)
	defer ts.Close()

	t.Run("generated when missing", func(t *testing.T) {
		resp, err := http.Get(ts.URL + "/health")
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		rid := resp.Header.Get(middleware.RequestIDHeader)
		if rid == "" {
			t.Fatal("expected X-Request-ID response header to be set")
		}
		if len(rid) < 8 {
			t.Fatalf("request id looks too short: %s", rid)
		}
	})

	t.Run("propagates client value", func(t *testing.T) {
		const customID = "test-request-id-abc123"
		req, err := http.NewRequest(http.MethodGet, ts.URL+"/health", nil)
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set(middleware.RequestIDHeader, customID)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if got := resp.Header.Get(middleware.RequestIDHeader); got != customID {
			t.Fatalf("expected X-Request-ID=%s, got %s", customID, got)
		}
	})
}

func TestAuthLoginIssuesValidJWT(t *testing.T) {
	cfg := config.TestConfig()
	ts := newTestServer(t, cfg)
	defer ts.Close()

	t.Run("valid credentials", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{
			"username": cfg.DevAuthUsername,
			"password": cfg.DevAuthPassword,
		})
		resp, err := http.Post(ts.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			raw, _ := io.ReadAll(resp.Body)
			t.Fatalf("expected 200, got %d body=%s", resp.StatusCode, raw)
		}

		var loginResp struct {
			AccessToken string `json:"access_token"`
			TokenType   string `json:"token_type"`
			ExpiresIn   int64  `json:"expires_in"`
			UserID      string `json:"user_id"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&loginResp); err != nil {
			t.Fatal(err)
		}
		if loginResp.AccessToken == "" {
			t.Fatal("expected access_token in response")
		}
		if loginResp.TokenType != "Bearer" {
			t.Fatalf("expected Bearer token type, got %s", loginResp.TokenType)
		}
		if loginResp.UserID != cfg.DevAuthUserID {
			t.Fatalf("expected user_id %s, got %s", cfg.DevAuthUserID, loginResp.UserID)
		}

		// Token must work on protected route.
		req, err := http.NewRequest(http.MethodGet, ts.URL+"/api/v1/status", nil)
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Authorization", "Bearer "+loginResp.AccessToken)
		statusResp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer statusResp.Body.Close()
		if statusResp.StatusCode != http.StatusOK {
			t.Fatalf("login token rejected: status %d", statusResp.StatusCode)
		}
	})

	t.Run("invalid credentials", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{
			"username": "wrong",
			"password": "wrong",
		})
		resp, err := http.Post(ts.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("expected 401, got %d", resp.StatusCode)
		}
	})

	t.Run("login is public no auth header needed", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{
			"username": cfg.DevAuthUsername,
			"password": cfg.DevAuthPassword,
		})
		resp, err := http.Post(ts.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode == http.StatusUnauthorized {
			t.Fatal("login should not require Authorization header")
		}
	})
}

func TestChatProxyStreamsFromPythonAPI(t *testing.T) {
	// Fake Python API backend.
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/chat/stream" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, ok := w.(http.Flusher)
		if !ok {
			t.Error("expected flusher")
			return
		}
		_, _ = w.Write([]byte("data: {\"type\":\"token\",\"content\":\"Hi\"}\n\n"))
		flusher.Flush()
		_, _ = w.Write([]byte("data: {\"type\":\"done\"}\n\n"))
		flusher.Flush()
	}))
	defer backend.Close()

	cfg := config.TestConfig()
	cfg.PythonAPIURL = backend.URL
	ts := newTestServer(t, cfg)
	defer ts.Close()

	token := issueTestToken(cfg)
	body, _ := json.Marshal(map[string]string{"message": "hello"})
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/v1/chat/stream", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		t.Fatalf("expected 200, got %d body=%s", resp.StatusCode, raw)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.Contains(ct, "text/event-stream") {
		t.Fatalf("expected event-stream content type, got %s", ct)
	}

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(raw), "token") {
		t.Fatalf("expected SSE token event in body, got %s", raw)
	}
}

func TestChatRequiresAuth(t *testing.T) {
	cfg := config.TestConfig()
	ts := newTestServer(t, cfg)
	defer ts.Close()

	body, _ := json.Marshal(map[string]string{"message": "hello"})
	resp, err := http.Post(ts.URL+"/api/v1/chat", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("expected 401 for unauthenticated chat, got %d", resp.StatusCode)
	}
}

func TestRequestValidationRejectsNonJSONPost(t *testing.T) {
	cfg := config.TestConfig()
	ts := newTestServer(t, cfg)
	defer ts.Close()

	token := issueTestToken(cfg)
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/v1/chat", strings.NewReader("not json"))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "text/plain")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusBadRequest {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("expected 400 for non-json content type, got %d body=%s", resp.StatusCode, body)
	}
}

// Ensure test helper logger doesn't panic.
func TestNewTestServerBuilds(t *testing.T) {
	cfg := config.TestConfig()
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	srv, err := server.New(cfg, logger, nil, server.Options{})
	if err != nil {
		t.Fatal(err)
	}
	if srv.Handler() == nil {
		t.Fatal("handler is nil")
	}
}
