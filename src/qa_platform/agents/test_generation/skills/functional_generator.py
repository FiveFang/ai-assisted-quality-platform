from __future__ import annotations

from typing import Any

import structlog

from .edge_case_generator import EdgeCaseGeneratorSkill
from .negative_scenario import NegativeScenarioSkill
from .positive_scenario import PositiveScenarioSkill

logger = structlog.get_logger()


class FunctionalGeneratorSkill:
    """
    Coordinator for functional test generation.
    Runs each selected sub-skill once against ALL requirements in a single LLM call,
    sequentially so they don't compete for rate-limit budget.
    """

    def __init__(self) -> None:
        self._positive = PositiveScenarioSkill()
        self._negative = NegativeScenarioSkill()
        self._edge_case = EdgeCaseGeneratorSkill()

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        rules: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        selected_skills: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        run_positive = selected_skills is None or "functional" in selected_skills
        run_negative = selected_skills is None or "negative" in selected_skills
        run_edge = selected_skills is None or "edge_case" in selected_skills

        functional_reqs = [r for r in requirements if r.get("type") == "FUNCTIONAL"]
        if not functional_reqs:
            return []

        logger.info("functional_generator.start", req_count=len(functional_reqs))
        all_cases: list[dict[str, Any]] = []

        if run_positive:
            try:
                cases = await self._positive.execute(functional_reqs, rules)
                all_cases.extend(cases)
                logger.info("functional_generator.positive.done", count=len(cases))
            except Exception as exc:
                logger.warning("functional_generator.positive.failed", error=str(exc))

        if run_negative:
            try:
                cases = await self._negative.execute(functional_reqs, rules)
                all_cases.extend(cases)
                logger.info("functional_generator.negative.done", count=len(cases))
            except Exception as exc:
                logger.warning("functional_generator.negative.failed", error=str(exc))

        if run_edge:
            try:
                cases = await self._edge_case.execute(functional_reqs, rules, entities)
                all_cases.extend(cases)
                logger.info("functional_generator.edge.done", count=len(cases))
            except Exception as exc:
                logger.warning("functional_generator.edge.failed", error=str(exc))

        logger.info("functional_generator.complete", test_count=len(all_cases))
        return all_cases
