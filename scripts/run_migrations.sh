#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DSN="${POSTGRES_DSN:-postgres://jarvis:jarvis@localhost:5432/jarvis?sslmode=disable}"

for f in "$ROOT"/go/migrations/*.sql; do
  echo "applying $(basename "$f")"
  psql "$DSN" -f "$f"
done

echo "migrations applied"
