#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DSN="${POSTGRES_DSN:-postgres://jarvis:jarvis@localhost:5432/jarvis?sslmode=disable}"

psql "$DSN" -f "$ROOT/go/migrations/001_request_logs.sql"
echo "migrations applied"
