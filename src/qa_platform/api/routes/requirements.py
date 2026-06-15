from __future__ import annotations

import asyncio
import time
from typing import Any

import anthropic
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agents.requirement_analysis.agent import RequirementAnalysisAgent
from ...infrastructure.review_store import review_store
from ...infrastructure.state_store import state_store
from ...schemas.common import ProcessingStatus
from ...schemas.requirements import NormalizedRequirement, RequirementSource

logger = structlog.get_logger()
router = APIRouter()

_raa = RequirementAnalysisAgent()


class AnalyzeRequest(BaseModel):
    source_type: str
    reference: str
    url: str | None = None
    raw_inputs: dict[str, Any]
    job_id: str | None = None
    max_tokens: int | None = None


class ReviewSignal(BaseModel):
    approved: bool
    reason: str | None = None


class RequirementSummary(BaseModel):
    requirement_id: str
    reference: str
    status: ProcessingStatus
    confidence_score: float
    created_at: str
    requirement_count: int
    human_review_required: bool
    test_suite_id: str | None = None


class ReviewEvent(BaseModel):
    id: str
    entity_key: str
    entity_type: str
    entity_id: str
    approved: bool
    reason: str | None
    created_at: str


@router.get("/", response_model=list[RequirementSummary])
async def list_requirements() -> list[RequirementSummary]:
    """List all analyzed requirements, newest first."""
    items = await state_store.list_by_prefix("normalized_requirement:")
    test_refs = await asyncio.gather(
        *[state_store.get(f"req_to_test:{item['requirement_id']}") for item in items]
    )
    return [
        RequirementSummary(
            requirement_id=item["requirement_id"],
            reference=item["source"]["reference"],
            status=item["status"],
            confidence_score=item["metadata"]["confidence_score"],
            created_at=item["metadata"]["created_at"],
            requirement_count=len(item.get("requirements", [])),
            human_review_required=item.get("human_review_required", False),
            test_suite_id=(ref or {}).get("test_suite_id"),
        )
        for item, ref in zip(items, test_refs)
    ]


@router.get("/progress/{job_id}")
async def get_analysis_progress(job_id: str) -> dict[str, Any]:
    """Return live progress for a running analysis job."""
    data = await state_store.get(f"analysis_progress:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job not found or not yet started")
    return data


@router.post("/analyze", response_model=NormalizedRequirement)
async def analyze_requirements(request: AnalyzeRequest) -> NormalizedRequirement:
    """Submit requirement artifacts for analysis. Returns NormalizedRequirement."""
    source = RequirementSource(
        type=request.source_type,
        reference=request.reference,
        url=request.url,
    )

    job_id = request.job_id
    start_time = time.monotonic()

    async def _on_progress(step: str, completed: list[str]) -> None:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {
                "current_step": step,
                "completed_steps": completed,
                "elapsed_seconds": round(time.monotonic() - start_time, 1),
                "status": "running",
            })

    try:
        result = await _raa.process(
            source=source,
            raw_inputs=request.raw_inputs,
            on_progress=_on_progress,
            max_tokens=request.max_tokens,
        )
    except anthropic.AuthenticationError:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": "API key invalid"})
        raise HTTPException(status_code=500, detail="Anthropic API key is invalid or missing.")
    except anthropic.BadRequestError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": exc.message})
        raise HTTPException(status_code=400, detail=f"AI API error: {exc.message}")
    except anthropic.RateLimitError:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": "Rate limit hit"})
        raise HTTPException(status_code=429, detail="Anthropic API rate limit hit — please try again in a moment.")
    except anthropic.APIStatusError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": exc.message})
        raise HTTPException(status_code=500, detail=f"Anthropic API returned an error ({exc.status_code}): {exc.message}")
    except ValueError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("analyze_requirements.unexpected_error", error=str(exc))
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    await state_store.set(f"normalized_requirement:{result.requirement_id}", result.model_dump(mode="json"))
    if job_id:
        await state_store.set(f"analysis_progress:{job_id}", {
            "current_step": None,
            "completed_steps": result.metadata.skills_executed,
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
            "status": "complete",
            "requirement_id": result.requirement_id,
        })
    return result


@router.get("/{requirement_id}/test-suite")
async def get_test_suite_for_requirement(requirement_id: str) -> dict[str, str]:
    """Return the test suite ID linked to this requirement, if one has been generated."""
    ref = await state_store.get(f"req_to_test:{requirement_id}")
    if not ref:
        raise HTTPException(status_code=404, detail="No test suite generated for this requirement")
    return ref


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
    entity_key = f"normalized_requirement:{requirement_id}"
    data = await state_store.get(entity_key)
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    new_status = ProcessingStatus.APPROVED if signal.approved else ProcessingStatus.REJECTED
    data["status"] = new_status.value
    if not signal.approved and signal.reason:
        data["review_reasons"] = data.get("review_reasons", []) + [signal.reason]

    await state_store.set(entity_key, data)
    await review_store.insert(
        entity_key=entity_key,
        entity_type="requirement",
        entity_id=requirement_id,
        approved=signal.approved,
        reason=signal.reason,
    )
    logger.info("requirement.review", requirement_id=requirement_id, approved=signal.approved)
    return {"requirement_id": requirement_id, "status": new_status.value}


@router.get("/{requirement_id}/review-history", response_model=list[ReviewEvent])
async def get_review_history(requirement_id: str) -> list[ReviewEvent]:
    """Return the full audit log of review decisions for a requirement."""
    events = await review_store.list_for_entity(f"normalized_requirement:{requirement_id}")
    return [ReviewEvent(**e) for e in events]
