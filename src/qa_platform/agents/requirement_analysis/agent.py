"""
Requirement Analysis Agent (RAA)

Orchestrates the full requirement analysis pipeline.
Skills are stateless; this agent owns execution order, parallelism, and state threading.

Execution sequence:
  1. Parse input artifacts (parallel by type)
  2. Extract requirements          [POWERFUL — most critical step]
  3. Extract workflows + rules + entities + RAG enrichment  (parallel)
  4. Detect ambiguities
  5. Score confidence
  6. Evaluate human escalation
  7. Assemble NormalizedRequirement
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from ...config import settings
from ...schemas.common import ProcessingStatus
from ...schemas.requirements import NormalizedRequirement, ProcessingMetadata, RequirementSource
from .skills.ambiguity_detector import AmbiguityDetectorSkill
from .skills.confidence_scorer import ConfidenceScorerSkill
from .skills.entity_extractor import EntityExtractorSkill
from .skills.jira_parser import JiraParserSkill
from .skills.json_generator import JSONGeneratorSkill
from .skills.openapi_parser import OpenAPIParserSkill
from .skills.prd_parser import PRDParserSkill
from .skills.rag_enricher import RAGEnricherSkill
from .skills.requirement_extractor import RequirementExtractorSkill
from .skills.rule_extractor import RuleExtractorSkill
from .skills.workflow_extractor import WorkflowExtractorSkill

logger = structlog.get_logger()


class RequirementAnalysisAgent:
    def __init__(self) -> None:
        self._prd_parser = PRDParserSkill()
        self._jira_parser = JiraParserSkill()
        self._openapi_parser = OpenAPIParserSkill()
        self._req_extractor = RequirementExtractorSkill()
        self._workflow_extractor = WorkflowExtractorSkill()
        self._rule_extractor = RuleExtractorSkill()
        self._entity_extractor = EntityExtractorSkill()
        self._ambiguity_detector = AmbiguityDetectorSkill()
        self._rag_enricher = RAGEnricherSkill()
        self._confidence_scorer = ConfidenceScorerSkill()
        self._json_generator = JSONGeneratorSkill()

    async def process(
        self,
        source: RequirementSource,
        raw_inputs: dict[str, Any],
    ) -> NormalizedRequirement:
        start = time.monotonic()
        log = logger.bind(source_type=source.type, reference=source.reference)
        log.info("raa.process.start")

        skills_executed: list[str] = []

        # Step 1 — parse input artifacts in parallel
        parse_coros: dict[str, Any] = {}
        if "prd" in raw_inputs:
            parse_coros["PRDParserSkill"] = self._prd_parser.execute(raw_inputs["prd"])
        if "jira" in raw_inputs:
            parse_coros["JiraParserSkill"] = self._jira_parser.execute(raw_inputs["jira"])
        if "openapi" in raw_inputs:
            parse_coros["OpenAPIParserSkill"] = self._openapi_parser.execute(raw_inputs["openapi"])

        if not parse_coros:
            raise ValueError("raw_inputs must contain at least one of: prd, jira, openapi")

        parsed_results = await asyncio.gather(*parse_coros.values())
        parsed = dict(zip(parse_coros.keys(), parsed_results))
        skills_executed.extend(parse_coros.keys())
        log.info("raa.parse.complete", parsers=list(parse_coros.keys()))

        # Step 2 — extract discrete requirements (POWERFUL tier)
        requirements = await self._req_extractor.execute(parsed)
        skills_executed.append("RequirementExtractorSkill")

        # Step 3 — parallel extraction + RAG enrichment
        (
            workflows,
            rules,
            entities,
            enriched_context,
        ) = await asyncio.gather(
            self._workflow_extractor.execute(requirements),
            self._rule_extractor.execute(requirements),
            self._entity_extractor.execute(parsed),
            self._rag_enricher.execute(requirements),
        )
        skills_executed.extend([
            "WorkflowExtractorSkill",
            "RuleExtractorSkill",
            "EntityExtractorSkill",
            "RAGEnricherSkill",
        ])

        # Step 4 — detect ambiguities
        ambiguities = await self._ambiguity_detector.execute(requirements, rules)
        skills_executed.append("AmbiguityDetectorSkill")

        # Step 5 — confidence scoring
        confidence = await self._confidence_scorer.execute(
            requirements=requirements,
            workflows=workflows,
            rules=rules,
            entities=entities,
            ambiguities=ambiguities,
        )
        skills_executed.append("ConfidenceScorerSkill")

        # Step 6 — escalation check
        human_review_required, review_reasons = self._evaluate_escalation(confidence, ambiguities)

        # Step 7 — assemble validated output
        duration_ms = int((time.monotonic() - start) * 1000)
        result = await self._json_generator.execute(
            source=source,
            requirements=requirements,
            workflows=workflows,
            rules=rules,
            entities=entities,
            ambiguities=ambiguities,
            enriched_context=enriched_context,
            metadata=ProcessingMetadata(
                confidence_score=confidence,
                processing_model=settings.default_model_tier.value,
                skills_executed=skills_executed,
                processing_duration_ms=duration_ms,
            ),
            status=(
                ProcessingStatus.AWAITING_REVIEW
                if human_review_required
                else ProcessingStatus.APPROVED
            ),
            human_review_required=human_review_required,
            review_reasons=review_reasons,
        )

        log.info(
            "raa.process.complete",
            requirement_id=result.requirement_id,
            confidence=confidence,
            human_review_required=human_review_required,
            duration_ms=duration_ms,
        )
        return result

    def _evaluate_escalation(
        self,
        confidence: float,
        ambiguities: list[dict[str, Any]],
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        blocking = [a for a in ambiguities if a.get("blocking")]
        high = [a for a in ambiguities if a.get("severity") in ("HIGH", "BLOCKING")]

        if confidence < settings.min_confidence_for_auto_proceed:
            reasons.append(
                f"Confidence {confidence:.2f} below threshold "
                f"{settings.min_confidence_for_auto_proceed}"
            )
        if blocking:
            reasons.append(f"{len(blocking)} blocking ambiguities require resolution")
        if len(high) > settings.max_ambiguities_for_auto_proceed:
            reasons.append(
                f"{len(high)} high-severity ambiguities exceed threshold "
                f"{settings.max_ambiguities_for_auto_proceed}"
            )

        return len(reasons) > 0, reasons
