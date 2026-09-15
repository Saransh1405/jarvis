package auth

import (
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

var (
	ErrInvalidToken = errors.New("invalid token")
	ErrExpiredToken = errors.New("token expired")
)

type Claims struct {
	UserID      string   `json:"user_id"`
	Email       string   `json:"email,omitempty"`
	Roles       []string `json:"roles,omitempty"`
	Permissions []string `json:"permissions,omitempty"`
	jwt.RegisteredClaims
}

type Validator struct {
	secret   []byte
	issuer   string
	audience string
}

func NewValidator(secret, issuer, audience string) *Validator {
	return &Validator{
		secret:   []byte(secret),
		issuer:   issuer,
		audience: audience,
	}
}

func (v *Validator) Validate(tokenStr string) (*Claims, error) {
	tokenStr = strings.TrimSpace(tokenStr)
	if tokenStr == "" {
		return nil, ErrInvalidToken
	}

	claims := &Claims{}
	opts := []jwt.ParserOption{jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()})}
	if v.issuer != "" {
		opts = append(opts, jwt.WithIssuer(v.issuer))
	}
	if v.audience != "" {
		opts = append(opts, jwt.WithAudience(v.audience))
	}

	token, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (interface{}, error) {
		if t.Method.Alg() != jwt.SigningMethodHS256.Alg() {
			return nil, fmt.Errorf("unexpected signing method: %s", t.Header["alg"])
		}
		return v.secret, nil
	}, opts...)
	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return nil, ErrExpiredToken
		}
		return nil, ErrInvalidToken
	}
	if !token.Valid {
		return nil, ErrInvalidToken
	}

	if claims.UserID == "" {
		return nil, ErrInvalidToken
	}

	return claims, nil
}

func (v *Validator) IssueToken(userID string, roles, permissions []string, ttl time.Duration) (string, error) {
	now := time.Now()
	claims := Claims{
		UserID:      userID,
		Roles:       roles,
		Permissions: permissions,
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    v.issuer,
			Audience:  jwt.ClaimStrings{v.audience},
			Subject:   userID,
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(ttl)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(v.secret)
}

func HasPermission(claims *Claims, permission string) bool {
	if claims == nil || permission == "" {
		return false
	}
	for _, p := range claims.Permissions {
		if p == permission || p == "*" {
			return true
		}
	}
	return false
}

func HasRole(claims *Claims, role string) bool {
	if claims == nil || role == "" {
		return false
	}
	for _, r := range claims.Roles {
		if r == role || r == "admin" {
			return true
		}
	}
	return false
}
