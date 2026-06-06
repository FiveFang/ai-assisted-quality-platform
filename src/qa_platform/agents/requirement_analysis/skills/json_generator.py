from __future__ import annotations

from typing import Any

import structlog
from pydantic import ValidationError

from ....schemas.common import ProcessingStatus
from ....schemas.requirements import (
    Ambiguity,
    BusinessRule,
    Dependency,
    Entity,
    EnrichedContext,
    NormalizedRequirement,
    ProcessingMetadata,
    Requirement,
    RequirementSource,
    Workflow,
    WorkflowStep,
)

logger = structlog.get_logger()


class JSONGeneratorSkill:
    """
    Assembles all extraction outputs into a schema-validated NormalizedRequirement.
    Centralizes Pydantic validation — if assembly fails here, returns FAILED status
    rather than propagating malformed data to the TGA.
    """

    async def execute(
        self,
        source: RequirementSource,
        requirements: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        rules: list[dict[str, Any]],
        entities: dict[str, Any],
        ambiguities: list[dict[str, Any]],
        enriched_context: dict[str, Any],
        metadata: ProcessingMetadata,
        status: ProcessingStatus,
        human_review_required: bool,
        review_reasons: list[str],
    ) -> NormalizedRequirement:
        logger.info("json_generator.start")
        try:
            result = NormalizedRequirement(
                source=source,
                metadata=metadata,
                status=status,
                requirements=[Requirement.model_validate(r) for r in requirements],
                entities=[Entity.model_validate(e) for e in entities.get("entities", [])],
                dependencies=[Dependency.model_validate(d) for d in entities.get("dependencies", [])],
                workflows=self._parse_workflows(workflows),
                business_rules=[BusinessRule.model_validate(r) for r in rules],
                ambiguities=[Ambiguity.model_validate(a) for a in ambiguities],
                enriched_context=EnrichedContext.model_validate(enriched_context),
                human_review_required=human_review_required,
                review_reasons=review_reasons,
            )
            logger.info("json_generator.complete", requirement_id=result.requirement_id)
            return result
        except ValidationError as exc:
            logger.error("json_generator.validation_failed", errors=exc.errors())
            raise

    def _parse_workflows(self, workflows: list[dict[str, Any]]) -> list[Workflow]:
        parsed = []
        for wf in workflows:
            steps = [WorkflowStep.model_validate(s) for s in wf.get("steps", [])]
            parsed.append(Workflow(
                workflow_id=wf["workflow_id"],
                name=wf["name"],
                description=wf.get("description", ""),
                steps=steps,
                happy_path=wf.get("happy_path", []),
                exception_paths=wf.get("exception_paths", []),
            ))
        return parsed
