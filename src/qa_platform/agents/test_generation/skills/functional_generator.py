from __future__ import annotations

from typing import Any

import structlog

from .positive_scenario import PositiveScenarioSkill
from .negative_scenario import NegativeScenarioSkill
from .edge_case_generator import EdgeCaseGeneratorSkill

logger = structlog.get_logger()


class FunctionalGeneratorSkill:
    """
    Coordinator skill for functional test generation.
    Invokes Positive, Negative, and EdgeCase skills per requirement,
    ensuring all scenario types are covered for every functional requirement.
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
    ) -> list[dict[str, Any]]:
        import asyncio

        functional_reqs = [
            r for r in requirements
            if r.get("type") == "FUNCTIONAL"
        ]
        logger.info("functional_generator.start", req_count=len(functional_reqs))

        all_cases: list[dict[str, Any]] = []
        for req in functional_reqs:
            pos, neg, edge = await asyncio.gather(
                self._positive.execute(req, rules),
                self._negative.execute(req, rules),
                self._edge_case.execute(req, rules, entities),
            )
            all_cases.extend(pos + neg + edge)

        logger.info("functional_generator.complete", test_count=len(all_cases))
        return all_cases
