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
from typing import Any, Awaitable, Callable

ProgressFn = Callable[[str, list[str]], Awaitable[None]]

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
        on_progress: ProgressFn | None = None,
        max_tokens: int | None = None,
    ) -> NormalizedRequirement:
        start = time.monotonic()
        log = logger.bind(source_type=source.type, reference=source.reference)
        log.info("raa.process.start")

        skills_executed: list[str] = []
        skill_warnings: list[str] = []

        async def _progress(step: str) -> None:
            if on_progress:
                try:
                    await on_progress(step, list(skills_executed))
                except Exception:
                    pass  # progress updates are best-effort

        await _progress("parsing")
        # Step 1 — parse input artifacts in parallel (per-parser fault tolerance)
        parse_coros: dict[str, Any] = {}
        if "prd" in raw_inputs:
            parse_coros["PRDParserSkill"] = self._prd_parser.execute(raw_inputs["prd"], max_tokens=max_tokens)
        if "jira" in raw_inputs:
            parse_coros["JiraParserSkill"] = self._jira_parser.execute(raw_inputs["jira"], max_tokens=max_tokens)
        if "openapi" in raw_inputs:
            parse_coros["OpenAPIParserSkill"] = self._openapi_parser.execute(raw_inputs["openapi"])

        if not parse_coros:
            raise ValueError("raw_inputs must contain at least one of: prd, jira, openapi")

        raw_parse = await asyncio.gather(*parse_coros.values(), return_exceptions=True)
        parsed: dict[str, Any] = {}
        for name, result in zip(parse_coros.keys(), raw_parse):
            if isinstance(result, BaseException):
                log.warning("raa.skill.failed", skill=name, error=str(result))
                skill_warnings.append(f"{name} failed: {result}")
            else:
                parsed[name] = result
                skills_executed.append(name)

        if not parsed:
            raise ValueError(
                f"All input parsers failed — cannot continue. Errors: {'; '.join(skill_warnings)}"
            )
        log.info("raa.parse.complete", parsers=list(parsed.keys()))
        await _progress("extracting")

        # Step 2 — extract discrete requirements (critical — failure aborts pipeline)
        requirements = await self._req_extractor.execute(parsed, max_tokens=max_tokens)
        skills_executed.append("RequirementExtractorSkill")
        await _progress("enriching")

        # Step 3 — parallel extraction + RAG enrichment (non-critical: degrade gracefully)
        _rag_default: dict[str, Any] = {
            "is_available": False,
            "similar_requirements": [],
            "relevant_domain_knowledge": [],
            "historical_test_patterns": [],
        }
        step3_names = ["WorkflowExtractorSkill", "RuleExtractorSkill", "EntityExtractorSkill", "RAGEnricherSkill"]
        step3_defaults: list[Any] = [[], [], [], _rag_default]
        step3_raw = await asyncio.gather(
            self._workflow_extractor.execute(requirements, max_tokens=max_tokens),
            self._rule_extractor.execute(requirements, max_tokens=max_tokens),
            self._entity_extractor.execute(parsed, max_tokens=max_tokens),
            self._rag_enricher.execute(requirements),
            return_exceptions=True,
        )
        step3_values: list[Any] = []
        for name, result, default in zip(step3_names, step3_raw, step3_defaults):
            if isinstance(result, BaseException):
                log.warning("raa.skill.failed", skill=name, error=str(result))
                skill_warnings.append(f"{name} failed: {result}")
                step3_values.append(default)
            else:
                skills_executed.append(name)
                step3_values.append(result)
        workflows, rules, entities, enriched_context = step3_values
        await _progress("ambiguities")

        # Step 4 — detect ambiguities (non-critical)
        try:
            ambiguities = await self._ambiguity_detector.execute(requirements, rules, max_tokens=max_tokens)
            skills_executed.append("AmbiguityDetectorSkill")
        except Exception as exc:
            log.warning("raa.skill.failed", skill="AmbiguityDetectorSkill", error=str(exc))
            skill_warnings.append(f"AmbiguityDetectorSkill failed: {exc}")
            ambiguities = []
        await _progress("scoring")

        # Step 5 — confidence scoring (non-critical; default 0.5 forces human review)
        try:
            confidence = await self._confidence_scorer.execute(
                requirements=requirements,
                workflows=workflows,
                rules=rules,
                entities=entities,
                ambiguities=ambiguities,
            )
            skills_executed.append("ConfidenceScorerSkill")
        except Exception as exc:
            log.warning("raa.skill.failed", skill="ConfidenceScorerSkill", error=str(exc))
            skill_warnings.append(f"ConfidenceScorerSkill failed: {exc}")
            confidence = 0.5

        await _progress("assembling")
        # Step 6 — escalation check; any skill failure forces human review
        human_review_required, review_reasons = self._evaluate_escalation(confidence, ambiguities)
        if skill_warnings:
            human_review_required = True
            review_reasons = [*review_reasons, *skill_warnings]

        # Step 7 — assemble validated output (critical)
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
            skills_failed=len(skill_warnings),
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
