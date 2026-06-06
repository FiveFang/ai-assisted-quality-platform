"""
Temporal activity definitions.
Each activity wraps a single agent execution — this is the retry boundary.
Activities are registered with the Temporal worker at startup.
"""
from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity

from ..agents.requirement_analysis.agent import RequirementAnalysisAgent
from ..agents.test_generation.agent import TestGenerationAgent
from ..infrastructure.state_store import state_store
from ..schemas.requirements import NormalizedRequirement, RequirementSource

logger = structlog.get_logger()

_raa = RequirementAnalysisAgent()
_tga = TestGenerationAgent()


@activity.defn
async def run_raa_activity(payload: dict[str, Any]) -> dict[str, Any]:
    logger.info("activity.raa.start")
    source = RequirementSource(**payload["source"])
    result: NormalizedRequirement = await _raa.process(
        source=source,
        raw_inputs=payload["raw_inputs"],
    )
    return result.model_dump(mode="json")


@activity.defn
async def run_tga_activity(normalized_dict: dict[str, Any]) -> dict[str, Any]:
    logger.info("activity.tga.start")
    normalized = NormalizedRequirement.model_validate(normalized_dict)
    result = await _tga.process(normalized)
    return result.model_dump(mode="json")


@activity.defn
async def store_normalized_requirement_activity(normalized_dict: dict[str, Any]) -> None:
    req_id = normalized_dict.get("requirement_id", "unknown")
    await state_store.set(f"normalized_requirement:{req_id}", normalized_dict)
    logger.info("activity.store_normalized.complete", requirement_id=req_id)


@activity.defn
async def store_test_suite_activity(suite_dict: dict[str, Any]) -> None:
    suite_id = suite_dict.get("test_suite_id", "unknown")
    await state_store.set(f"test_suite:{suite_id}", suite_dict)
    logger.info("activity.store_test_suite.complete", test_suite_id=suite_id)
