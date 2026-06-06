from __future__ import annotations

import uuid
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from ..config import settings

logger = structlog.get_logger()


class VectorStore:
    """
    Qdrant-backed store for RAG context enrichment.
    Embeds requirements with sentence-transformers; retrieves by cosine similarity.
    """

    _VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension

    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self._encoder = SentenceTransformer(settings.embedding_model)
        self._collection = settings.qdrant_collection

    async def ensure_collection(self) -> None:
        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}
        if self._collection not in existing:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("vector_store.collection_created", collection=self._collection)

    def _embed(self, text: str) -> list[float]:
        return self._encoder.encode(text).tolist()  # type: ignore[return-value]

    async def upsert_requirement(
        self,
        requirement_id: str,
        text: str,
        payload: dict[str, Any],
    ) -> None:
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=self._embed(text),
            payload={"requirement_id": requirement_id, **payload},
        )
        await self._client.upsert(collection_name=self._collection, points=[point])

    async def search_similar(
        self,
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query_filter: Filter | None = None
        if filter_tags:
            query_filter = Filter(
                must=[
                    FieldCondition(key="tags", match=MatchValue(value=tag))
                    for tag in filter_tags
                ]
            )

        results = await self._client.search(
            collection_name=self._collection,
            query_vector=self._embed(query_text),
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        return [{"score": r.score, "payload": r.payload} for r in results]


vector_store = VectorStore()
