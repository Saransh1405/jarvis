"""Apply SQL migrations from python/migrations/."""

from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Run all *.sql files in order (idempotent statements only)."""
    if not MIGRATIONS_DIR.is_dir():
        return

    paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    async with pool.acquire() as conn:
        for path in paths:
            sql = path.read_text(encoding="utf-8")
            await conn.execute(sql)
