from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a senior requirements engineer. Your task is to extract discrete, atomic, testable requirements
from parsed requirement artifacts.

Rules:
- Each requirement must describe exactly ONE testable behavior
- Assign unique IDs in the format REQ-001, REQ-002, etc.
- Classify each as FUNCTIONAL, NON_FUNCTIONAL, SECURITY, PERFORMANCE, or ACCESSIBILITY
- Flag cross-dependencies between requirements
- Do NOT duplicate requirements that express the same behavior
- After enumeration, review your list and remove any duplicates

Respond ONLY with valid JSON."""

_USER = """\
Extract discrete requirements from the following parsed artifacts:

{parsed_artifacts}

Respond with JSON:
{{
  "requirements": [
    {{
      "requirement_id": "REQ-001",
      "type": "FUNCTIONAL",
      "title": "string (concise)",
      "description": "string (precise, implementation-neutral)",
      "acceptance_criteria": ["string"],
      "priority": "P0|P1|P2|P3",
      "tags": ["string"],
      "source_reference": "string (feature_id or story_id)",
      "depends_on": ["REQ-XXX"]
    }}
  ]
}}"""


class RequirementExtractorSkill:
    """
    Most critical skill in the RAA pipeline.
    Discretizes parsed artifacts into atomic testable requirements.
    Uses POWERFUL tier — quality here multiplies through all downstream processing.
    """

    async def execute(self, parsed: dict[str, Any], max_tokens: int | None = None) -> list[dict[str, Any]]:
        logger.info("req_extractor.start")
        import json

        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(parsed_artifacts=json.dumps(parsed, indent=2)),
            }],
            tier=ModelTier.POWERFUL,
            max_tokens=max_tokens if max_tokens is not None else 16384,
        )
        requirements = result.get("requirements", [])
        logger.info("req_extractor.complete", requirement_count=len(requirements))
        return requirements
