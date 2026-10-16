package handlers

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"jarvis-go/internal/db/redis"
	"jarvis-go/internal/gateway/response"

	"github.com/gin-gonic/gin"
)

const (
	telegramSecretHeader = "X-Telegram-Bot-Api-Secret-Token"
	internalTokenHeader  = "X-Internal-Token"
	telegramDedupeTTL    = 7 * 24 * time.Hour
)

// TelegramHandler verifies Telegram webhooks and forwards them to the Python service.
type TelegramHandler struct {
	Secret        string
	InternalToken string
	PythonAPIURL  string
	Redis         *redis.Client
	HTTP          *http.Client
	Logger        *slog.Logger
}

func (h *TelegramHandler) Webhook(c *gin.Context) {
	if h.Secret == "" {
		response.Error(c, http.StatusServiceUnavailable, "telegram_unconfigured", "telegram webhook secret is not configured")
		return
	}
	if !secretMatches(c.GetHeader(telegramSecretHeader), h.Secret) {
		response.Unauthorized(c, "invalid webhook secret")
		return
	}

	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		response.BadRequest(c, "invalid_body", "failed to read request body")
		return
	}

	var payload struct {
		UpdateID int64 `json:"update_id"`
	}
	_ = json.Unmarshal(body, &payload)
	if payload.UpdateID > 0 && h.Redis != nil {
		fresh, err := h.Redis.SetNX(c.Request.Context(), "tg:upd:"+strconv.FormatInt(payload.UpdateID, 10), "1", telegramDedupeTTL)
		if err == nil && !fresh {
			c.JSON(http.StatusOK, gin.H{"ok": true, "duplicate": true})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{"ok": true})
	if h.PythonAPIURL == "" {
		return
	}
	copied := append([]byte(nil), body...)
	go h.forward(copied)
}

func (h *TelegramHandler) forward(body []byte) {
	if h.InternalToken == "" {
		h.log().Error("telegram forward skipped; INTERNAL_API_TOKEN is empty")
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, h.PythonAPIURL+"/internal/channels/inbound", bytes.NewReader(body))
	if err != nil {
		h.log().Error("telegram forward request", "error", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set(internalTokenHeader, h.InternalToken)

	client := h.HTTP
	if client == nil {
		client = &http.Client{Timeout: 2 * time.Minute}
	}
	resp, err := client.Do(req)
	if err != nil {
		h.log().Error("telegram forward failed", "error", err)
		return
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	if resp.StatusCode >= 300 {
		h.log().Error("telegram forward status", "status", resp.StatusCode)
	}
}

func (h *TelegramHandler) log() *slog.Logger {
	if h.Logger != nil {
		return h.Logger
	}
	return slog.Default()
}

func secretMatches(got, want string) bool {
	if want == "" {
		return false
	}
	gotSum := sha256.Sum256([]byte(got))
	wantSum := sha256.Sum256([]byte(want))
	return hmac.Equal(gotSum[:], wantSum[:])
}
