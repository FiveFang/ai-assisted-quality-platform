from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import structlog
from pgvector.asyncpg import register_vector
from sentence_transformers import SentenceTransformer

from ..config import settings

logger = structlog.get_logger()


class VectorStore:
    """
    PostgreSQL + pgvector backed store for RAG context enrichment.
    Embeds requirements with sentence-transformers; retrieves by cosine similarity.
    """

    _VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension

    def __init__(self) -> None:
        self._encoder: SentenceTransformer | None = None
        self._table = settings.vector_table
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()

    def _get_encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            self._encoder = SentenceTransformer(settings.embedding_model)
        return self._encoder

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(
                    settings.database_url,
                    init=register_vector,
                )
        return self._pool  # type: ignore[return-value]

    async def ensure_collection(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    requirement_id TEXT UNIQUE NOT NULL,
                    tags TEXT[],
                    payload JSONB NOT NULL,
                    embedding VECTOR({self._VECTOR_SIZE})
                )
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {self._table}_embedding_idx
                ON {self._table} USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
        logger.info("vector_store.collection_ensured", table=self._table)

    def _embed(self, text: str) -> list[float]:
        return self._get_encoder().encode(text).tolist()  # type: ignore[return-value]

    async def upsert_requirement(
        self,
        requirement_id: str,
        text: str,
        payload: dict[str, Any],
    ) -> None:
        pool = await self._get_pool()
        embedding = self._embed(text)
        tags = payload.get("tags", [])
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self._table} (requirement_id, tags, payload, embedding)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (requirement_id) DO UPDATE
                    SET tags = EXCLUDED.tags,
                        payload = EXCLUDED.payload,
                        embedding = EXCLUDED.embedding
                """,
                requirement_id,
                tags,
                json.dumps({"requirement_id": requirement_id, **payload}),
                embedding,
            )

    async def search_similar(
        self,
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        embedding = self._embed(query_text)

        tag_filter = "AND tags @> $4::text[]" if filter_tags else ""
        params: list[Any] = [embedding, score_threshold, top_k]
        if filter_tags:
            params.append(filter_tags)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT payload, 1 - (embedding <=> $1::vector) AS score
                FROM {self._table}
                WHERE 1 - (embedding <=> $1::vector) >= $2
                {tag_filter}
                ORDER BY score DESC
                LIMIT $3
                """,
                *params,
            )

        return [
            {"score": float(row["score"]), "payload": json.loads(row["payload"])}
            for row in rows
        ]


vector_store = VectorStore()
