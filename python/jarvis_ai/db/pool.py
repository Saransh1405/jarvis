"""Postgres connection pool (asyncpg)."""

import asyncpg


async def create_pool(database_url: str) -> asyncpg.Pool:
    if not database_url:
        raise ValueError("database_url is required")
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10)
