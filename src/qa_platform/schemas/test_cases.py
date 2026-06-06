from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import new_id


class TestStep(BaseModel):
    step_number: int
    action: str
    expected_result: str
    test_data: dict[str, Any] | None = None


class Assertion(BaseModel):
    assertion_id: str = Field(default_factory=lambda: new_id("ASSERT"))
    description: str
    assertion_type: str  # STATUS_CODE | RESPONSE_BODY | DATABASE | UI_ELEMENT | RESPONSE_TIME_MS
    expected_value: Any
    operator: str  # EQUALS | CONTAINS | MATCHES_SCHEMA | IS_NOT_NULL | LESS_THAN


class AutomationScaffold(BaseModel):
    framework: str  # PLAYWRIGHT | APPIUM | PYTEST | KARATE
    language: str = "python"
    scaffold_code: str
    file_path_suggestion: str
    imports: list[str] = Field(default_factory=list)
    fixtures_required: list[str] = Field(default_factory=list)


class TestCase(BaseModel):
    test_id: str = Field(default_factory=lambda: new_id("TC"))
    source_requirement_id: str
    type: str  # FUNCTIONAL | API | SECURITY | UI | MOBILE | EDGE_CASE | NEGATIVE
    priority: str = "P2"  # P0–P3
    title: str
    description: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep]
    expected_results: list[str]
    assertions: list[Assertion] = Field(default_factory=list)
    test_data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    automation_scaffold: AutomationScaffold | None = None
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_duplicate: bool = False
    duplicate_of: str | None = None


class TestSuiteMetadata(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generation_model: str
    total_test_cases: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    coverage_estimate: float = Field(ge=0.0, le=1.0)
    human_review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class TestSuite(BaseModel):
    """Canonical output contract of the TGA."""

    test_suite_id: str = Field(default_factory=lambda: new_id("TS"))
    source_requirement_id: str
    metadata: TestSuiteMetadata
    test_cases: list[TestCase]
