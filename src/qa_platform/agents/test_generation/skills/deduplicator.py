from __future__ import annotations

from typing import Any

import structlog
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from ....config import settings

logger = structlog.get_logger()

_SIMILARITY_THRESHOLD = 0.92


class DeduplicatorSkill:
    """
    Identifies semantically duplicate test cases across skill outputs.
    Embeds title+description, computes pairwise cosine similarity.
    Keeps the case with more assertions/steps; marks the other as duplicate.
    """

    def __init__(self) -> None:
        self._encoder: SentenceTransformer | None = None

    def _get_encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            self._encoder = SentenceTransformer(settings.embedding_model)
        return self._encoder

    async def execute(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(test_cases) < 2:
            return test_cases

        logger.info("deduplicator.start", test_count=len(test_cases))

        texts = [
            f"{tc.get('title', '')} {tc.get('description', '')}"
            for tc in test_cases
        ]
        embeddings = self._get_encoder().encode(texts)
        sim_matrix = cosine_similarity(embeddings)

        duplicate_of: dict[int, int] = {}
        for i in range(len(test_cases)):
            if i in duplicate_of:
                continue
            for j in range(i + 1, len(test_cases)):
                if j in duplicate_of:
                    continue
                if sim_matrix[i][j] >= _SIMILARITY_THRESHOLD:
                    # keep the richer case
                    score_i = self._richness(test_cases[i])
                    score_j = self._richness(test_cases[j])
                    loser = j if score_i >= score_j else i
                    winner = i if loser == j else j
                    duplicate_of[loser] = winner

        result = []
        for idx, tc in enumerate(test_cases):
            tc_copy = dict(tc)
            if idx in duplicate_of:
                tc_copy["is_duplicate"] = True
                winner_id = test_cases[duplicate_of[idx]].get("test_id", str(duplicate_of[idx]))
                tc_copy["duplicate_of"] = winner_id
            result.append(tc_copy)

        dupes = sum(1 for tc in result if tc.get("is_duplicate"))
        logger.info("deduplicator.complete", duplicates_found=dupes)
        return result

    def _richness(self, tc: dict[str, Any]) -> int:
        return len(tc.get("assertions", [])) + len(tc.get("steps", []))
