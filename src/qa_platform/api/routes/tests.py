from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agents.test_generation.agent import TestGenerationAgent
from ...infrastructure.state_store import state_store
from ...schemas.requirements import NormalizedRequirement
from ...schemas.test_cases import TestSuite

logger = structlog.get_logger()
router = APIRouter()

_tga = TestGenerationAgent()


class GenerateRequest(BaseModel):
    requirement_id: str


class ReviewSignal(BaseModel):
    approved: bool
    reason: str | None = None


@router.post("/generate", response_model=TestSuite)
async def generate_tests(request: GenerateRequest) -> TestSuite:
    """Generate test suite from an approved NormalizedRequirement."""
    data = await state_store.get(f"normalized_requirement:{request.requirement_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found")

    if data.get("status") not in ("APPROVED", "AWAITING_REVIEW"):
        raise HTTPException(
            status_code=422,
            detail=f"Requirement status '{data.get('status')}' cannot be sent to TGA. Must be APPROVED.",
        )

    normalized = NormalizedRequirement.model_validate(data)
    suite = await _tga.process(normalized)
    await state_store.set(f"test_suite:{suite.test_suite_id}", suite.model_dump(mode="json"))
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
    status = "APPROVED" if approved_flag else "REJECTED"
    logger.info("test_suite.review", test_suite_id=test_suite_id, approved=approved_flag)
    return {"test_suite_id": test_suite_id, "status": status}
