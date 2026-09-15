package middleware

import (
	"sync"

	"jarvis-go/internal/gateway/response"

	"github.com/gin-gonic/gin"
	"golang.org/x/time/rate"
)

func RateLimit(deps Deps) gin.HandlerFunc {
	if deps.Config == nil || !deps.Config.RateLimitEnabled {
		return func(c *gin.Context) { c.Next() }
	}

	local := &localLimiter{
		limiters: make(map[string]*rate.Limiter),
		rps:      deps.Config.RateLimitRPS,
		burst:    deps.Config.RateLimitBurst,
	}

	return func(c *gin.Context) {
		key := c.ClientIP()
		if deps.Redis != nil {
			allowed, err := deps.Redis.Allow(
				c.Request.Context(),
				key,
				deps.Config.RateLimitRPS,
				deps.Config.RateLimitBurst,
			)
			if err == nil {
				if !allowed {
					response.TooManyRequests(c)
					return
				}
				c.Next()
				return
			}
		}

		if !local.allow(key) {
			response.TooManyRequests(c)
			return
		}
		c.Next()
	}
}

type localLimiter struct {
	mu       sync.Mutex
	limiters map[string]*rate.Limiter
	rps      float64
	burst    int
}

func (l *localLimiter) allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()

	lim, ok := l.limiters[key]
	if !ok {
		lim = rate.NewLimiter(rate.Limit(l.rps), l.burst)
		l.limiters[key] = lim
	}
	return lim.Allow()
}
