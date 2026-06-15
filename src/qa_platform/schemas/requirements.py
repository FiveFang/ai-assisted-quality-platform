from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import (
    AmbiguitySeverity,
    ProcessingStatus,
    RequirementType,
    SourceType,
    new_id,
)


class RequirementSource(BaseModel):
    type: SourceType
    reference: str
    url: str | None = None
    raw_content_hash: str | None = None


class ProcessingMetadata(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0"
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_model: str
    skills_executed: list[str] = Field(default_factory=list)
    processing_duration_ms: int | None = None


class Entity(BaseModel):
    name: str
    type: str  # USER | SERVICE | DATA_MODEL | EXTERNAL_SYSTEM
    attributes: list[str] = Field(default_factory=list)
    description: str | None = None


class WorkflowStep(BaseModel):
    step_id: str
    action: str
    actor: str
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)


class Workflow(BaseModel):
    workflow_id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    happy_path: list[str]
    exception_paths: list[list[str]] = Field(default_factory=list)


class BusinessRule(BaseModel):
    rule_id: str
    description: str
    rule_type: str  # VALIDATION | AUTHORIZATION | COMPUTATION | CONSTRAINT
    applies_to: list[str]
    is_explicit: bool = True
    confidence: float = Field(ge=0.0, le=1.0)


class Dependency(BaseModel):
    dependency_id: str
    name: str
    type: str  # API | DATABASE | SERVICE | LIBRARY
    version: str | None = None
    criticality: str  # REQUIRED | OPTIONAL


class APIEndpoint(BaseModel):
    method: str
    path: str
    summary: str | None = None
    request_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    auth_required: bool = False
    error_responses: dict[str, Any] = Field(default_factory=dict)


class Ambiguity(BaseModel):
    ambiguity_id: str
    description: str
    severity: AmbiguitySeverity
    affected_requirement: str
    suggested_clarification: str
    blocking: bool = False


class EnrichedContext(BaseModel):
    is_available: bool = True
    similar_requirements: list[dict[str, Any]] = Field(default_factory=list)
    relevant_domain_knowledge: list[str] = Field(default_factory=list)
    historical_test_patterns: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    requirement_id: str = Field(default_factory=lambda: new_id("REQ"))
    type: RequirementType
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: str = "P2"
    tags: list[str] = Field(default_factory=list)
    source_reference: str | None = None


class NormalizedRequirement(BaseModel):
    """Canonical output contract of the RAA. Consumed by the TGA."""

    requirement_id: str = Field(default_factory=lambda: new_id("NR"))
    source: RequirementSource
    metadata: ProcessingMetadata
    status: ProcessingStatus

    requirements: list[Requirement]
    entities: list[Entity] = Field(default_factory=list)
    workflows: list[Workflow] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    api_contracts: list[APIEndpoint] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    enriched_context: EnrichedContext = Field(default_factory=EnrichedContext)

    human_review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    rejected_requirements: dict[str, str | None] = Field(default_factory=dict)
