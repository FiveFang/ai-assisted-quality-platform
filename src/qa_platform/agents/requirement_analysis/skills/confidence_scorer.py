from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class ConfidenceScorerSkill:
    """
    Computes a holistic confidence score (0.0–1.0) for the requirement analysis.

    Scoring formula (weights sum to 1.0):
      source_completeness  0.25  — how much of the expected structure was parseable
      entity_coverage      0.25  — entities found vs requirements referencing entities
      rule_coverage        0.30  — rules found vs acceptance criteria items
      ambiguity_penalty    0.20  — penalized by high/blocking ambiguity count
    """

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        rules: list[dict[str, Any]],
        entities: dict[str, Any],
        ambiguities: list[dict[str, Any]],
    ) -> float:
        source_completeness = self._score_completeness(requirements)
        entity_coverage = self._score_entity_coverage(requirements, entities)
        rule_coverage = self._score_rule_coverage(requirements, rules)
        ambiguity_penalty = self._score_ambiguity_penalty(ambiguities)

        score = (
            source_completeness * 0.25
            + entity_coverage * 0.25
            + rule_coverage * 0.30
            + ambiguity_penalty * 0.20
        )
        score = round(min(max(score, 0.0), 1.0), 4)
        logger.info(
            "confidence_scorer.result",
            score=score,
            source_completeness=source_completeness,
            entity_coverage=entity_coverage,
            rule_coverage=rule_coverage,
            ambiguity_penalty=ambiguity_penalty,
        )
        return score

    def _score_completeness(self, requirements: list[dict[str, Any]]) -> float:
        if not requirements:
            return 0.0
        required_fields = {"requirement_id", "type", "title", "description", "acceptance_criteria"}
        scores = [
            len(required_fields & req.keys()) / len(required_fields)
            for req in requirements
        ]
        return sum(scores) / len(scores)

    def _score_entity_coverage(
        self,
        requirements: list[dict[str, Any]],
        entities: dict[str, Any],
    ) -> float:
        entity_names = {e["name"].lower() for e in entities.get("entities", [])}
        if not entity_names:
            return 0.5  # neutral — no entities expected for simple requirements
        refs = 0
        covered = 0
        for req in requirements:
            desc = (req.get("description", "") + " ".join(req.get("tags", []))).lower()
            for name in entity_names:
                if name in desc:
                    refs += 1
                    covered += 1
                    break
        return covered / max(refs, 1)

    def _score_rule_coverage(
        self,
        requirements: list[dict[str, Any]],
        rules: list[dict[str, Any]],
    ) -> float:
        total_criteria = sum(len(r.get("acceptance_criteria", [])) for r in requirements)
        if total_criteria == 0:
            return 0.5
        rule_count = len(rules)
        # expect roughly 1 rule per 2 acceptance criteria items
        expected = total_criteria / 2
        return min(rule_count / max(expected, 1), 1.0)

    def _score_ambiguity_penalty(self, ambiguities: list[dict[str, Any]]) -> float:
        penalty = 0.0
        for a in ambiguities:
            severity = a.get("severity", "LOW")
            if severity == "BLOCKING":
                penalty += 0.3
            elif severity == "HIGH":
                penalty += 0.1
            elif severity == "MEDIUM":
                penalty += 0.05
        return max(1.0 - penalty, 0.0)
