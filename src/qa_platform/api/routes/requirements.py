from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ...agents.requirement_analysis.agent import RequirementAnalysisAgent
from ...infrastructure.state_store import state_store
from ...schemas.common import ProcessingStatus, SourceType
from ...schemas.requirements import NormalizedRequirement, RequirementSource

logger = structlog.get_logger()
router = APIRouter()

_raa = RequirementAnalysisAgent()


class AnalyzeRequest(BaseModel):
    source_type: SourceType
    reference: str
    url: str | None = None
    raw_inputs: dict[str, Any]


class ReviewSignal(BaseModel):
    approved: bool
    reason: str | None = None


@router.post("/analyze", response_model=NormalizedRequirement)
async def analyze_requirements(request: AnalyzeRequest) -> NormalizedRequirement:
    """Submit requirement artifacts for analysis. Returns NormalizedRequirement."""
    source = RequirementSource(
        type=request.source_type,
        reference=request.reference,
        url=request.url,
    )
    result = await _raa.process(source=source, raw_inputs=request.raw_inputs)
    await state_store.set(f"normalized_requirement:{result.requirement_id}", result.model_dump(mode="json"))
    return result


@router.get("/{requirement_id}", response_model=NormalizedRequirement)
async def get_requirement(requirement_id: str) -> NormalizedRequirement:
    """Retrieve a previously analyzed requirement by ID."""
    data = await state_store.get(f"normalized_requirement:{requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return NormalizedRequirement.model_validate(data)


@router.post("/{requirement_id}/review")
async def review_requirement(requirement_id: str, signal: ReviewSignal) -> dict[str, str]:
    """Human review signal for RAA output. Approves or rejects for downstream processing."""
    data = await state_store.get(f"normalized_requirement:{requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    new_status = ProcessingStatus.APPROVED if signal.approved else ProcessingStatus.REJECTED
    data["status"] = new_status.value
    if not signal.approved and signal.reason:
        data["review_reasons"] = data.get("review_reasons", []) + [signal.reason]

    await state_store.set(f"normalized_requirement:{requirement_id}", data)
    logger.info("requirement.review", requirement_id=requirement_id, approved=signal.approved)
    return {"requirement_id": requirement_id, "status": new_status.value}
