from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a senior QA architect specializing in edge case discovery. Think deeply about system
behavior at boundaries and under unusual-but-valid conditions. Focus on:
- Boundary values (min, max, min±1, max±1)
- Concurrent/parallel operations on the same resource
- Timezone, locale, and character encoding variations
- Pagination boundaries and empty result sets
- Long-running operations and timeout conditions
- Re-entrancy and idempotency (retry same operation twice)

Respond ONLY with valid JSON."""

_USER = """\
Generate edge case test cases for:

Requirement: {requirement}
Business rules: {rules}
Relevant entities: {entities}

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "EDGE_CASE",
      "title": "string",
      "description": "string (include which edge condition this targets)",
      "preconditions": ["string"],
      "steps": [
        {{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}
      ],
      "expected_results": ["string"],
      "test_data": {{}},
      "tags": ["edge-case"]
    }}
  ]
}}"""


class EdgeCaseGeneratorSkill:
    """
    Generates boundary and unusual-condition test cases.
    Uses POWERFUL tier — edge cases require deeper reasoning about failure modes.
    """

    async def execute(
        self,
        requirement: dict[str, Any],
        rules: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    requirement=json.dumps(requirement, indent=2),
                    rules=json.dumps(rules, indent=2),
                    entities=json.dumps(entities, indent=2),
                ),
            }],
            tier=ModelTier.POWERFUL,
        )
        cases = result.get("test_cases", [])
        for case in cases:
            case["source_requirement_id"] = requirement.get("requirement_id", "")
        return cases
