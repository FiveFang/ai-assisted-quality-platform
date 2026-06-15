"""
Audit log for human review decisions.

Every approve/reject action on a NormalizedRequirement or TestSuite is written
here as an immutable event. The main state store holds the current status;
this store holds the full history.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from ..config import settings

logger = structlog.get_logger()

_TABLE = "review_events"


class InMemoryReviewStore:
    """Non-durable fallback — events lost on process restart."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def insert(
        self,
        *,
        entity_key: str,
        entity_type: str,
        entity_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> None:
        self._events.append({
            "id": str(uuid.uuid4()),
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "approved": approved,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    async def list_for_entity(self, entity_key: str) -> list[dict[str, Any]]:
        return [e for e in self._events if e["entity_key"] == entity_key]


class PostgresReviewStore:
    """
    Immutable append-only audit log backed by PostgreSQL.

    Table schema:
        review_events (
            id          UUID PRIMARY KEY,
            entity_key  TEXT NOT NULL,   -- full state_store key
            entity_type TEXT NOT NULL,   -- "requirement" | "test_suite"
            entity_id   TEXT NOT NULL,   -- "NR-..." | "TS-..."
            approved    BOOLEAN NOT NULL,
            reason      TEXT,
            created_at  TIMESTAMPTZ DEFAULT now()
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
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    entity_key  TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id   TEXT NOT NULL,
                    approved    BOOLEAN NOT NULL,
                    reason      TEXT,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {_TABLE}_entity_idx
                ON {_TABLE} (entity_key, created_at DESC)
            """)
        logger.info("review_store.table_ensured", table=_TABLE)

    async def insert(
        self,
        *,
        entity_key: str,
        entity_type: str,
        entity_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {_TABLE} (entity_key, entity_type, entity_id, approved, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                entity_key, entity_type, entity_id, approved, reason,
            )
        logger.info(
            "review_event.recorded",
            entity_key=entity_key,
            approved=approved,
        )

    async def list_for_entity(self, entity_key: str) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, entity_key, entity_type, entity_id, approved, reason, created_at
                FROM {_TABLE}
                WHERE entity_key = $1
                ORDER BY created_at DESC
                """,
                entity_key,
            )
        return [
            {
                "id": str(row["id"]),
                "entity_key": row["entity_key"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "approved": row["approved"],
                "reason": row["reason"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


class ReviewStore:
    """Proxy — Postgres when available, in-memory otherwise."""

    def __init__(self) -> None:
        self._backend: InMemoryReviewStore | PostgresReviewStore = InMemoryReviewStore()

    async def upgrade_to_postgres(self) -> None:
        pg = PostgresReviewStore()
        await pg.ensure_table()
        self._backend = pg
        logger.info("review_store.using_postgres")

    async def insert(
        self,
        *,
        entity_key: str,
        entity_type: str,
        entity_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> None:
        await self._backend.insert(
            entity_key=entity_key,
            entity_type=entity_type,
            entity_id=entity_id,
            approved=approved,
            reason=reason,
        )

    async def list_for_entity(self, entity_key: str) -> list[dict[str, Any]]:
        return await self._backend.list_for_entity(entity_key)


review_store = ReviewStore()
