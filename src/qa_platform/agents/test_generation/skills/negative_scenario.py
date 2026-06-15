from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA engineer generating negative test cases. Negative tests verify the system correctly
handles invalid inputs, unauthorized access, state violations, and missing required data.
Each case must specify the expected error behavior. Respond ONLY with valid JSON."""

_USER = """\
Generate negative test cases for this requirement:

Requirement: {requirement}

Business rules: {rules}

Cover these categories:
- Missing required fields
- Invalid data types or formats
- Out-of-range or boundary-violating values
- Unauthorized access attempts
- State violations (wrong preconditions)

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "NEGATIVE",
      "title": "string",
      "description": "string",
      "preconditions": ["string"],
      "steps": [
        {{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}
      ],
      "expected_results": ["string (must include expected error/rejection behavior)"],
      "test_data": {{}},
      "tags": ["negative"]
    }}
  ]
}}"""


class NegativeScenarioSkill:
    """Generates invalid-input and error-path test cases for a single requirement."""

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
