package proxy

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"jarvis-go/internal/gateway/response"
	"jarvis-go/internal/observability"

	"github.com/gin-gonic/gin"
)

const (
	requestIDHeader = "X-Request-ID"
	forwardTimeout  = 5 * time.Minute
)

type Client struct {
	baseURL    string
	httpClient *http.Client
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: forwardTimeout,
		},
	}
}

func (p *Client) Forward(c *gin.Context, backendPath string) {
	p.doForward(c, backendPath, false)
}

func (p *Client) ForwardStream(c *gin.Context, backendPath string) {
	p.doForward(c, backendPath, true)
}

func (p *Client) doForward(c *gin.Context, backendPath string, stream bool) {
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		response.BadRequest(c, "invalid_body", "failed to read request body")
		return
	}

	url := p.baseURL + backendPath
	req, err := http.NewRequestWithContext(c.Request.Context(), c.Request.Method, url, bytes.NewReader(body))
	if err != nil {
		response.InternalError(c)
		return
	}

	copyForwardHeaders(c, req)
	if len(body) > 0 {
		req.ContentLength = int64(len(body))
	}

	resp, err := p.httpClient.Do(req)
	if err != nil {
		response.Error(c, http.StatusBadGateway, "upstream_error", "python api unavailable")
		return
	}
	defer resp.Body.Close()

	copyResponseHeaders(resp, c)
	c.Status(resp.StatusCode)

	if stream {
		flusher, ok := c.Writer.(http.Flusher)
		if !ok {
			response.InternalError(c)
			return
		}
		buf := make([]byte, 4096)
		for {
			n, readErr := resp.Body.Read(buf)
			if n > 0 {
				if _, writeErr := c.Writer.Write(buf[:n]); writeErr != nil {
					return
				}
				flusher.Flush()
			}
			if readErr != nil {
				if readErr != io.EOF {
					c.Error(fmt.Errorf("stream read: %w", readErr))
				}
				return
			}
		}
	}

	if _, err := io.Copy(c.Writer, resp.Body); err != nil {
		c.Error(fmt.Errorf("copy response: %w", err))
	}
}

func copyForwardHeaders(c *gin.Context, req *http.Request) {
	req.Header.Set("Content-Type", c.GetHeader("Content-Type"))
	if auth := c.GetHeader("Authorization"); auth != "" {
		req.Header.Set("Authorization", auth)
	}

	if rid := observability.RequestIDFromContext(c.Request.Context()); rid != "" {
		req.Header.Set(requestIDHeader, rid)
	} else if rid := c.GetHeader(requestIDHeader); rid != "" {
		req.Header.Set(requestIDHeader, rid)
	}

	if uid := observability.UserIDFromContext(c.Request.Context()); uid != "" {
		req.Header.Set("X-User-ID", uid)
	}
}

func copyResponseHeaders(resp *http.Response, c *gin.Context) {
	for _, key := range []string{"Content-Type", "Cache-Control", "X-Request-ID"} {
		if v := resp.Header.Get(key); v != "" {
			c.Header(key, v)
		}
	}
}
