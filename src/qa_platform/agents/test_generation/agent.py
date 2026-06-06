"""
Test Generation Agent (TGA)

Consumes NormalizedRequirement from the RAA and produces a structured TestSuite.
Skills run in parallel by domain; post-processing (assertions, dedup, prioritization,
scaffolding) runs sequentially after all generators complete.

Execution sequence:
  1. Parallel domain generation: functional, API, security, UI/mobile
  2. Assertion enrichment
  3. Deduplication
  4. Risk-based prioritization
  5. Test formatting (schema validation)
  6. Scaffold generation (P0/P1 non-duplicates only)
  7. Human review gate
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from typing import Any

import structlog

from ...config import settings
from ...schemas.requirements import NormalizedRequirement
from ...schemas.test_cases import TestCase, TestSuite, TestSuiteMetadata
from .skills.api_test_generator import APITestGeneratorSkill
from .skills.assertion_generator import AssertionGeneratorSkill
from .skills.deduplicator import DeduplicatorSkill
from .skills.functional_generator import FunctionalGeneratorSkill
from .skills.mobile_ui_generator import MobileUIGeneratorSkill
from .skills.risk_prioritizer import RiskPriorizerSkill
from .skills.scaffold_generator import ScaffoldGeneratorSkill
from .skills.security_test_generator import SecurityTestGeneratorSkill
from .skills.test_formatter import TestFormatterSkill

logger = structlog.get_logger()


class TestGenerationAgent:
    def __init__(self) -> None:
        self._functional = FunctionalGeneratorSkill()
        self._api = APITestGeneratorSkill()
        self._security = SecurityTestGeneratorSkill()
        self._mobile_ui = MobileUIGeneratorSkill()
        self._assertion_gen = AssertionGeneratorSkill()
        self._deduplicator = DeduplicatorSkill()
        self._prioritizer = RiskPriorizerSkill()
        self._formatter = TestFormatterSkill()
        self._scaffold_gen = ScaffoldGeneratorSkill()

    async def process(self, normalized: NormalizedRequirement) -> TestSuite:
        start = time.monotonic()
        log = logger.bind(requirement_id=normalized.requirement_id)
        log.info("tga.process.start")

        requirements = [r.model_dump() for r in normalized.requirements]
        rules = [r.model_dump() for r in normalized.business_rules]
        entities = [e.model_dump() for e in normalized.entities]
        api_contracts = [a.model_dump() for a in normalized.api_contracts]
        workflows = [w.model_dump() for w in normalized.workflows]

        # Step 1 — parallel domain generation
        functional_cases, api_cases, security_cases, ui_cases = await asyncio.gather(
            self._functional.execute(requirements, rules, entities),
            self._api.execute(api_contracts),
            self._security.execute(requirements, api_contracts, entities),
            self._mobile_ui.execute(workflows, requirements),
        )

        raw_cases: list[dict[str, Any]] = (
            functional_cases + api_cases + security_cases + ui_cases
        )
        log.info("tga.generation.complete", raw_count=len(raw_cases))

        # Step 2 — assertion enrichment
        raw_cases = await self._assertion_gen.execute(raw_cases)

        # Step 3 — deduplication
        raw_cases = await self._deduplicator.execute(raw_cases)

        # Step 4 — risk prioritization
        raw_cases = await self._prioritizer.execute(raw_cases)

        # Step 5 — schema validation + formatting
        test_cases: list[TestCase] = await self._formatter.execute(raw_cases)

        # Step 6 — scaffold generation for P0/P1
        test_cases = await self._scaffold_gen.execute(test_cases)

        # Step 7 — build TestSuite with review gate
        human_review_required, review_reasons = self._evaluate_review_gate(
            normalized, test_cases
        )

        by_type = dict(Counter(tc.type for tc in test_cases))
        by_priority = dict(Counter(tc.priority for tc in test_cases))

        duration_ms = int((time.monotonic() - start) * 1000)
        suite = TestSuite(
            source_requirement_id=normalized.requirement_id,
            metadata=TestSuiteMetadata(
                generation_model=settings.default_model_tier.value,
                total_test_cases=len(test_cases),
                by_type=by_type,
                by_priority=by_priority,
                coverage_estimate=self._estimate_coverage(test_cases, requirements),
                human_review_required=human_review_required,
                review_reasons=review_reasons,
            ),
            test_cases=test_cases,
        )

        log.info(
            "tga.process.complete",
            test_suite_id=suite.test_suite_id,
            total=len(test_cases),
            human_review_required=human_review_required,
            duration_ms=duration_ms,
        )
        return suite

    def _evaluate_review_gate(
        self,
        normalized: NormalizedRequirement,
        test_cases: list[TestCase],
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if normalized.metadata.confidence_score < settings.min_confidence_for_auto_proceed:
            reasons.append("Source requirement confidence below threshold")
        if not test_cases:
            reasons.append("No test cases generated — likely requires manual investigation")

        p0_count = sum(1 for tc in test_cases if tc.priority == "P0")
        if p0_count == 0 and any(
            "security" in r.get("tags", []) or "payment" in r.get("tags", [])
            for r in [req.model_dump() for req in normalized.requirements]
        ):
            reasons.append("Security/payment requirements present but no P0 tests generated")

        return len(reasons) > 0, reasons

    def _estimate_coverage(
        self,
        test_cases: list[TestCase],
        requirements: list[dict[str, Any]],
    ) -> float:
        if not requirements:
            return 0.0
        req_ids = {r["requirement_id"] for r in requirements}
        covered = {
            tc.source_requirement_id
            for tc in test_cases
            if tc.source_requirement_id in req_ids
        }
        return round(len(covered) / len(req_ids), 4)
