from __future__ import annotations

from typing import Any

import structlog

from ....infrastructure.vector_store import vector_store

logger = structlog.get_logger()


class RAGEnricherSkill:
    """
    Enriches current requirements with similar historical context from Qdrant.
    Prevents rediscovering known failure modes; surfaces institutional test patterns.
    """

    async def execute(self, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        logger.info("rag_enricher.start", req_count=len(requirements))

        all_similar: list[dict[str, Any]] = []
        domain_knowledge: set[str] = set()
        test_patterns: set[str] = set()
        is_available = True

        for req in requirements:
            query = f"{req.get('title', '')} {req.get('description', '')}"
            try:
                results = await vector_store.search_similar(
                    query_text=query,
                    top_k=3,
                    score_threshold=0.7,
                )
            except Exception as exc:
                logger.warning("rag_enricher.vector_store_unavailable", error=str(exc))
                is_available = False
                break
            for r in results:
                all_similar.append({
                    "requirement_id": r["payload"].get("requirement_id"),
                    "similarity": r["score"],
                    "test_outcome": r["payload"].get("test_outcome"),
                })
                domain_knowledge.update(r["payload"].get("domain_knowledge", []))
                test_patterns.update(r["payload"].get("test_patterns", []))

        enriched = {
            "is_available": is_available,
            "similar_requirements": all_similar,
            "relevant_domain_knowledge": list(domain_knowledge),
            "historical_test_patterns": list(test_patterns),
        }
        logger.info("rag_enricher.complete", similar_count=len(all_similar), is_available=is_available)
        return enriched
