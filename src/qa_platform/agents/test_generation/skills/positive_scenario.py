from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA engineer generating positive test cases. Positive tests verify correct system behavior
when all preconditions are met and inputs are valid. Each test case must be specific, deterministic,
and independently executable. Respond ONLY with valid JSON."""

_USER = """\
Generate positive test cases for this requirement:

Requirement: {requirement}

Business rules to satisfy: {rules}

Generate 2-4 positive test cases covering the main happy paths.

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "FUNCTIONAL",
      "title": "string",
      "description": "string",
      "preconditions": ["string"],
      "steps": [
        {{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}
      ],
      "expected_results": ["string"],
      "test_data": {{}},
      "tags": ["positive", "functional"]
    }}
  ]
}}"""


class PositiveScenarioSkill:
    """Generates valid-input, expected-success test cases for a single requirement."""

    async def execute(
        self,
        requirement: dict[str, Any],
        rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    requirement=json.dumps(requirement, indent=2),
                    rules=json.dumps(rules, indent=2),
                ),
            }],
            tier=ModelTier.FAST,
        )
        cases = result.get("test_cases", [])
        for case in cases:
            case["source_requirement_id"] = requirement.get("requirement_id", "")
        return cases
