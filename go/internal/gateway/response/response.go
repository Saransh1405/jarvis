package response

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

type ErrorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type ErrorResponse struct {
	Error ErrorBody `json:"error"`
}

func JSON(c *gin.Context, status int, body any) {
	c.JSON(status, body)
}

func Error(c *gin.Context, status int, code, message string) {
	c.AbortWithStatusJSON(status, ErrorResponse{
		Error: ErrorBody{
			Code:    code,
			Message: message,
		},
	})
}

func BadRequest(c *gin.Context, code, message string) {
	Error(c, http.StatusBadRequest, code, message)
}

func Unauthorized(c *gin.Context, message string) {
	Error(c, http.StatusUnauthorized, "unauthorized", message)
}

func Forbidden(c *gin.Context, message string) {
	Error(c, http.StatusForbidden, "forbidden", message)
}

func TooManyRequests(c *gin.Context) {
	Error(c, http.StatusTooManyRequests, "rate_limit_exceeded", "too many requests")
}

func InternalError(c *gin.Context) {
	Error(c, http.StatusInternalServerError, "internal_error", "internal server error")
}
