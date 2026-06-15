from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agents.test_generation.agent import TestGenerationAgent
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
from ...schemas.requirements import NormalizedRequirement
from ...schemas.test_cases import TestSuite

logger = structlog.get_logger()
router = APIRouter()

_tga = TestGenerationAgent()


class GenerateRequest(BaseModel):
    requirement_id: str
    model: str | None = None  # "provider:model_id" override; None = tier-based routing


class ReviewSignal(BaseModel):
    approved: bool
    reason: str | None = None


@router.post("/generate", response_model=TestSuite)
async def generate_tests(request: GenerateRequest) -> TestSuite:
    """Generate test suite from an approved NormalizedRequirement."""
    model_override = resolve_model_override(request.model)

    data = await state_store.get(f"normalized_requirement:{request.requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    if data.get("status") not in ("APPROVED", "AWAITING_REVIEW"):
        raise HTTPException(
            status_code=422,
            detail=f"Requirement status '{data.get('status')}' cannot be sent to TGA. Must be APPROVED.",
        )

    normalized = NormalizedRequirement.model_validate(data)

    # Strip rejected items before handing off to TGA
    rejected_ids = set(normalized.rejected_requirements.keys())
    if rejected_ids:
        normalized = normalized.model_copy(update={
            "requirements": [r for r in normalized.requirements if r.requirement_id not in rejected_ids],
        })
        logger.info(
            "generate_tests.skipping_rejected",
            count=len(rejected_ids),
            remaining=len(normalized.requirements),
        )
    if not normalized.requirements:
        raise HTTPException(
            status_code=422,
            detail="All requirements have been rejected — nothing to generate tests for.",
        )

    try:
        with use_model(model_override):
            suite = await _tga.process(normalized)
    except LLMAuthError as exc:
        raise HTTPException(status_code=500, detail=f"{(exc.provider or 'LLM').title()} API key is invalid or missing.")
    except LLMBadRequestError as exc:
        raise HTTPException(status_code=400, detail=f"AI API error: {exc.message}")
    except LLMRateLimitError:
        raise HTTPException(status_code=429, detail="LLM API rate limit hit — please try again in a moment.")
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"LLM request timed out: {exc.message}")
    except LLMError as exc:
        status = exc.status_code or "unknown"
        raise HTTPException(status_code=502, detail=f"{(exc.provider or 'LLM').title()} API error ({status}): {exc.message}")

    await state_store.set(f"test_suite:{suite.test_suite_id}", suite.model_dump(mode="json"))
    await state_store.set(
        f"req_to_test:{request.requirement_id}",
        {"test_suite_id": suite.test_suite_id},
    )
    return suite


@router.get("/{test_suite_id}", response_model=TestSuite)
async def get_test_suite(test_suite_id: str) -> TestSuite:
    """Retrieve a generated test suite by ID."""
    data = await state_store.get(f"test_suite:{test_suite_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return TestSuite.model_validate(data)


@router.post("/{test_suite_id}/review")
async def review_test_suite(test_suite_id: str, signal: ReviewSignal) -> dict[str, str]:
    """Human review signal for TGA output."""
    data = await state_store.get(f"test_suite:{test_suite_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Test suite not found")

    approved_flag = signal.approved
    data["metadata"]["human_review_required"] = not approved_flag
    if not approved_flag and signal.reason:
        data["metadata"]["review_reasons"] = (
            data["metadata"].get("review_reasons", []) + [signal.reason]
        )

    await state_store.set(f"test_suite:{test_suite_id}", data)
    await review_store.insert(
        entity_key=f"test_suite:{test_suite_id}",
        entity_type="test_suite",
        entity_id=test_suite_id,
        approved=approved_flag,
        reason=signal.reason,
    )
    status = "APPROVED" if approved_flag else "REJECTED"
    logger.info("test_suite.review", test_suite_id=test_suite_id, approved=approved_flag)
    return {"test_suite_id": test_suite_id, "status": status}
