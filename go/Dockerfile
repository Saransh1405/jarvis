# syntax=docker/dockerfile:1

FROM golang:1.23-alpine AS builder

WORKDIR /src

ENV GOTOOLCHAIN=auto \
    CGO_ENABLED=0

RUN apk add --no-cache ca-certificates git

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-s -w" \
    -trimpath \
    -o /out/gateway \
    ./cmd/gateway

FROM alpine:3.20

RUN apk add --no-cache ca-certificates wget \
    && adduser -D -u 65532 -g '' appuser

COPY --from=builder /out/gateway /gateway

USER 65532

EXPOSE 8080

ENTRYPOINT ["/gateway"]
