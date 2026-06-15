from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agents.requirement_analysis.agent import RequirementAnalysisAgent
from ...infrastructure import job_registry
from ...infrastructure.llm_client import use_model
from ...infrastructure.llm_errors import (
    LLMAuthError,
    LLMBadRequestError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from ...infrastructure.review_store import review_store
from ...infrastructure.state_store import state_store
from .meta import resolve_model_override
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
    model: str | None = None  # "provider:model_id" override; None = tier-based routing


class ReviewSignal(BaseModel):
    approved: bool
    reason: str | None = None


class RejectItemRequest(BaseModel):
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

    # Validate the optional model override up front (400 if key/SDK missing)
    model_override = resolve_model_override(request.model)

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

    if job_id:
        job_registry.register(job_id, asyncio.current_task())  # type: ignore[arg-type]

    try:
        with use_model(model_override):
            result = await _raa.process(
                source=source,
                raw_inputs=request.raw_inputs,
                on_progress=_on_progress,
                max_tokens=request.max_tokens,
            )
    except asyncio.CancelledError:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "cancelled", "error": "Cancelled by user"})
        raise HTTPException(status_code=499, detail="Analysis cancelled by user")
    except LLMAuthError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": "API key invalid"})
        raise HTTPException(status_code=500, detail=f"{(exc.provider or 'LLM').title()} API key is invalid or missing.")
    except LLMBadRequestError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": exc.message})
        raise HTTPException(status_code=400, detail=f"AI API error: {exc.message}")
    except LLMRateLimitError:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": "Rate limit hit"})
        raise HTTPException(status_code=429, detail="LLM API rate limit hit — please try again in a moment.")
    except LLMTimeoutError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": "Request timed out"})
        raise HTTPException(status_code=504, detail=f"LLM request timed out: {exc.message}")
    except LLMError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": exc.message})
        status = exc.status_code or "unknown"
        raise HTTPException(status_code=502, detail=f"{(exc.provider or 'LLM').title()} API error ({status}): {exc.message}")
    except ValueError as exc:
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("analyze_requirements.unexpected_error", error=str(exc))
        if job_id:
            await state_store.set(f"analysis_progress:{job_id}", {"status": "failed", "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
    finally:
        if job_id:
            job_registry.unregister(job_id)

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


@router.post("/{requirement_id}/items/{item_id}/reject")
async def reject_requirement_item(
    requirement_id: str, item_id: str, body: RejectItemRequest
) -> dict[str, str]:
    """Mark a single extracted requirement as rejected. Rejected items are skipped by TGA."""
    data = await state_store.get(f"normalized_requirement:{requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    item_ids = {r["requirement_id"] for r in data.get("requirements", [])}
    if item_id not in item_ids:
        raise HTTPException(status_code=404, detail=f"Requirement item '{item_id}' not found")

    rejected = dict(data.get("rejected_requirements", {}))
    rejected[item_id] = body.reason
    data["rejected_requirements"] = rejected
    await state_store.set(f"normalized_requirement:{requirement_id}", data)
    await review_store.insert(
        entity_key=f"normalized_requirement:{requirement_id}",
        entity_type="requirement_item",
        entity_id=item_id,
        approved=False,
        reason=body.reason,
    )
    logger.info("requirement_item.rejected", requirement_id=requirement_id, item_id=item_id)
    return {"requirement_id": requirement_id, "item_id": item_id, "status": "rejected"}


@router.delete("/{requirement_id}/items/{item_id}/reject")
async def unreject_requirement_item(requirement_id: str, item_id: str) -> dict[str, str]:
    """Remove the rejection on a single extracted requirement."""
    data = await state_store.get(f"normalized_requirement:{requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    rejected = dict(data.get("rejected_requirements", {}))
    rejected.pop(item_id, None)
    data["rejected_requirements"] = rejected
    await state_store.set(f"normalized_requirement:{requirement_id}", data)
    await review_store.insert(
        entity_key=f"normalized_requirement:{requirement_id}",
        entity_type="requirement_item",
        entity_id=item_id,
        approved=True,
        reason="Rejection reversed",
    )
    logger.info("requirement_item.unrejected", requirement_id=requirement_id, item_id=item_id)
    return {"requirement_id": requirement_id, "item_id": item_id, "status": "active"}


@router.post("/{requirement_id}/rerun/{skill_key}", response_model=NormalizedRequirement)
async def rerun_skill(requirement_id: str, skill_key: str) -> NormalizedRequirement:
    """Re-run a single failed skill without re-processing the entire pipeline."""
    data = await state_store.get(f"normalized_requirement:{requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    valid_skills = {"ambiguity_detector", "rule_extractor", "workflow_extractor"}
    if skill_key not in valid_skills:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill_key}' cannot be re-run. Valid options: {', '.join(sorted(valid_skills))}",
        )

    requirement = NormalizedRequirement.model_validate(data)
    try:
        result = await _raa.rerun_skill(skill_key=skill_key, requirement=requirement)
    except Exception as exc:
        logger.exception("rerun_skill.failed", skill_key=skill_key, requirement_id=requirement_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Skill re-run failed: {exc}")

    await state_store.set(f"normalized_requirement:{requirement_id}", result.model_dump(mode="json"))
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
