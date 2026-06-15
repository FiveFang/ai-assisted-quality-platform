"""
State persistence for pipeline results.

PostgresStateStore is the production backend — a single JSONB table in the same
Postgres instance used by pgvector. InMemoryStateStore is the fallback when
Postgres is unavailable.

StateStore (the module-level singleton) starts as in-memory and is upgraded to
Postgres during application startup. Callers import `state_store` and never
reference the backend directly.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import structlog

from ..config import settings

logger = structlog.get_logger()

_TABLE = "platform_state"


class InMemoryStateStore:
    """Non-durable fallback — data lost on process restart."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        logger.debug("state.set", key=key, backend="memory")

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def list_by_prefix(self, prefix: str) -> list[Any]:
        return [v for k, v in self._store.items() if k.startswith(prefix)]


class PostgresStateStore:
    """
    JSONB key-value store backed by PostgreSQL.

    Table schema:
        platform_state (
            key        TEXT PRIMARY KEY,       -- e.g. "normalized_requirement:NR-..."
            value      JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(settings.database_url)
        return self._pool  # type: ignore[return-value]

    async def ensure_table(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {_TABLE} (
                    key        TEXT PRIMARY KEY,
                    value      JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {_TABLE}_type_idx
                ON {_TABLE} (split_part(key, ':', 1))
            """)
        logger.info("state_store.table_ensured", table=_TABLE)

    async def set(self, key: str, value: Any) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {_TABLE} (key, value, updated_at)
                VALUES ($1, $2::jsonb, now())
                ON CONFLICT (key) DO UPDATE
                    SET value      = EXCLUDED.value,
                        updated_at = now()
                """,
                key,
                json.dumps(value),
            )
        logger.debug("state.set", key=key, backend="postgres")

    async def get(self, key: str) -> Any | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT value FROM {_TABLE} WHERE key = $1", key
            )
        return json.loads(row["value"]) if row else None

    async def delete(self, key: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {_TABLE} WHERE key = $1", key)
        logger.debug("state.delete", key=key, backend="postgres")

    async def list_by_prefix(self, prefix: str) -> list[Any]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT value FROM {_TABLE} WHERE key LIKE $1 ORDER BY created_at DESC",
                f"{prefix}%",
            )
        return [json.loads(row["value"]) for row in rows]


class StateStore:
    """
    Proxy that delegates to Postgres when available, in-memory otherwise.
    Call upgrade_to_postgres() on application startup.
    """

    def __init__(self) -> None:
        self._backend: InMemoryStateStore | PostgresStateStore = InMemoryStateStore()

    async def upgrade_to_postgres(self) -> None:
        pg = PostgresStateStore()
        await pg.ensure_table()
        self._backend = pg
        logger.info("state_store.using_postgres")

    async def set(self, key: str, value: Any) -> None:
        await self._backend.set(key, value)

    async def get(self, key: str) -> Any | None:
        return await self._backend.get(key)

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)

    async def list_by_prefix(self, prefix: str) -> list[Any]:
        return await self._backend.list_by_prefix(prefix)


state_store = StateStore()
