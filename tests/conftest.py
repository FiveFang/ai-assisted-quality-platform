from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from qa_platform.schemas.common import ProcessingStatus, RequirementType, SourceType
from qa_platform.schemas.requirements import (
    NormalizedRequirement,
    ProcessingMetadata,
    Requirement,
    RequirementSource,
)
from qa_platform.schemas.test_cases import TestCase, TestStep


@pytest.fixture
def sample_source() -> RequirementSource:
    return RequirementSource(type=SourceType.PRD, reference="test-prd-001")


@pytest.fixture
def sample_metadata() -> ProcessingMetadata:
    return ProcessingMetadata(
        confidence_score=0.85,
        processing_model="balanced",
        skills_executed=["PRDParserSkill", "RequirementExtractorSkill"],
    )


@pytest.fixture
def sample_requirement() -> Requirement:
    return Requirement(
        requirement_id="REQ-001",
        type=RequirementType.FUNCTIONAL,
        title="User can add item to cart",
        description="Authenticated users can add any in-stock product to their cart.",
        acceptance_criteria=["Cart count incremented", "Item persists across sessions"],
        priority="P1",
        tags=["cart", "checkout"],
    )


@pytest.fixture
def sample_normalized(
    sample_source: RequirementSource,
    sample_metadata: ProcessingMetadata,
    sample_requirement: Requirement,
) -> NormalizedRequirement:
    return NormalizedRequirement(
        source=sample_source,
        metadata=sample_metadata,
        status=ProcessingStatus.APPROVED,
        requirements=[sample_requirement],
    )


@pytest.fixture
def sample_test_case() -> TestCase:
    return TestCase(
        source_requirement_id="REQ-001",
        type="FUNCTIONAL",
        priority="P1",
        title="Authenticated user adds item to empty cart",
        description="Verify adding an in-stock item to an empty cart",
        preconditions=["User is authenticated", "Cart is empty"],
        steps=[
            TestStep(step_number=1, action="Navigate to product page", expected_result="Page loads"),
            TestStep(step_number=2, action="Click Add to Cart", expected_result="Cart count = 1"),
        ],
        expected_results=["Cart contains 1 item"],
    )
