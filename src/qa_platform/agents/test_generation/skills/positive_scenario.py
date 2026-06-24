from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA engineer. Generate positive (happy-path) test cases for the given requirements.
For each requirement produce the 2-3 most important success scenarios.
Each test case must include the source_requirement_id matching one of the requirement_ids provided.
Respond ONLY with valid JSON."""

_USER = """\
Generate positive test cases for:

Requirements: {requirements}
Business rules: {rules}

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "FUNCTIONAL",
      "title": "string",
      "description": "string",
      "source_requirement_id": "string",
      "preconditions": ["string"],
      "steps": [{{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}],
      "expected_results": ["string"],
      "test_data": {{}},
      "tags": ["positive", "functional"]
    }}
  ]
}}"""


class PositiveScenarioSkill:
    """Generates positive (happy-path) test cases in a single LLM call for all requirements."""

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        if not requirements:
            return []

        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    requirements=json.dumps(requirements, indent=2),
                    rules=json.dumps(rules, indent=2),
                ),
            }],
            tier=ModelTier.BALANCED,
            max_tokens=32768,
        )
        cases = result.get("test_cases", [])
        logger.info("positive_scenario.complete", test_count=len(cases))
        return cases
