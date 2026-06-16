"""
Test Generation Agent (TGA)

Consumes NormalizedRequirement from the RAA and produces a structured TestSuite.
Skills run sequentially by domain so they don't compete for LLM rate-limit budget.
Post-processing (assertions, dedup, prioritization, scaffolding) also runs sequentially.
Every step is individually guarded: a failure in one step preserves whatever test
cases were already collected rather than discarding everything.

Execution sequence:
  1. Sequential domain generation (only selected skill groups):
       functional (positive + negative + edge case) → api → security → ui
  2. Assertion enrichment
  3. Deduplication
  4. Risk-based prioritization
  5. Test formatting (schema validation)
  6. Scaffold generation (P0/P1 non-duplicates only)
  7. Human review gate
"""
from __future__ import annotations

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

    async def process(
        self,
        normalized: NormalizedRequirement,
        selected_skills: set[str] | None = None,
        selected_requirement_ids: list[str] | None = None,
    ) -> TestSuite:
        """
        Generate a TestSuite from a NormalizedRequirement.

        selected_skills: which domain generators to run (None = all six).
          Valid values: "functional", "negative", "edge_case", "api", "security", "ui"
        selected_requirement_ids: which requirements to include (None = all non-rejected).
        """
        start = time.monotonic()
        log = logger.bind(requirement_id=normalized.requirement_id)
        log.info(
            "tga.process.start",
            selected_skills=sorted(selected_skills) if selected_skills else "all",
            selected_req_count=len(selected_requirement_ids) if selected_requirement_ids is not None else "all",
        )

        requirements = [r.model_dump() for r in normalized.requirements]

        # Apply user-selected requirement filter before handing off to skills.
        if selected_requirement_ids is not None:
            req_id_set = set(selected_requirement_ids)
            requirements = [r for r in requirements if r["requirement_id"] in req_id_set]
            log.info("tga.requirements.filtered", count=len(requirements))

        rules = [r.model_dump() for r in normalized.business_rules]
        entities = [e.model_dump() for e in normalized.entities]
        api_contracts = [a.model_dump() for a in normalized.api_contracts]
        workflows = [w.model_dump() for w in normalized.workflows]

        # Determine which top-level skill groups to run.
        # "functional" group covers the three sub-types (functional/negative/edge_case).
        run_functional = selected_skills is None or bool(
            selected_skills & {"functional", "negative", "edge_case"}
        )
        run_api = selected_skills is None or "api" in selected_skills
        run_security = selected_skills is None or "security" in selected_skills
        run_ui = selected_skills is None or "ui" in selected_skills

        # Step 1 — sequential domain generation (one group at a time to avoid rate-limit
        # competition between groups; within each group the semaphore still applies).
        # Each group is wrapped individually so a failure doesn't discard other groups' output.
        raw_cases: list[dict[str, Any]] = []
        skill_errors: list[str] = []

        if run_functional:
            try:
                cases = await self._functional.execute(requirements, rules, entities, selected_skills)
                raw_cases.extend(cases)
                log.info("tga.functional.done", count=len(cases))
            except Exception as exc:
                log.warning("tga.functional.failed", error=str(exc))
                skill_errors.append(f"functional: {exc}")

        if run_api:
            try:
                cases = await self._api.execute(api_contracts)
                raw_cases.extend(cases)
                log.info("tga.api.done", count=len(cases))
            except Exception as exc:
                log.warning("tga.api.failed", error=str(exc))
                skill_errors.append(f"api: {exc}")

        if run_security:
            try:
                cases = await self._security.execute(requirements, api_contracts, entities)
                raw_cases.extend(cases)
                log.info("tga.security.done", count=len(cases))
            except Exception as exc:
                log.warning("tga.security.failed", error=str(exc))
                skill_errors.append(f"security: {exc}")

        if run_ui:
            try:
                cases = await self._mobile_ui.execute(workflows, requirements)
                raw_cases.extend(cases)
                log.info("tga.ui.done", count=len(cases))
            except Exception as exc:
                log.warning("tga.ui.failed", error=str(exc))
                skill_errors.append(f"ui: {exc}")

        log.info("tga.generation.complete", raw_count=len(raw_cases))

        # Steps 2-6 — post-processing. Each step falls back gracefully so a single
        # LLM failure doesn't throw away everything collected above.

        # Step 2 — assertion enrichment
        try:
            raw_cases = await self._assertion_gen.execute(raw_cases)
        except Exception as exc:
            log.warning("tga.assertion_gen.failed", error=str(exc))

        # Step 3 — deduplication
        try:
            raw_cases = await self._deduplicator.execute(raw_cases)
        except Exception as exc:
            log.warning("tga.deduplicator.failed", error=str(exc))

        # Step 4 — risk prioritization
        try:
            raw_cases = await self._prioritizer.execute(raw_cases)
        except Exception as exc:
            log.warning("tga.prioritizer.failed", error=str(exc))

        # Step 5 — schema validation + formatting
        test_cases: list[TestCase] = []
        try:
            test_cases = await self._formatter.execute(raw_cases)
        except Exception as exc:
            log.warning("tga.formatter.failed", error=str(exc))

        # Step 6 — scaffold generation for P0/P1
        try:
            test_cases = await self._scaffold_gen.execute(test_cases)
        except Exception as exc:
            log.warning("tga.scaffold_gen.failed", error=str(exc))

        # Step 7 — build TestSuite with review gate
        human_review_required, review_reasons = self._evaluate_review_gate(
            normalized, test_cases, skill_errors
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
        skill_errors: list[str] | None = None,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if normalized.metadata.confidence_score < settings.min_confidence_for_auto_proceed:
            reasons.append("Source requirement confidence below threshold")
        if skill_errors:
            for err in skill_errors:
                reasons.append(f"Skill error — {err}")
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
