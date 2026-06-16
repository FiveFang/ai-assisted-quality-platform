from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a senior QA architect. Generate edge case test cases for the given requirements.
Cover: boundary values (min/max/±1), concurrent operations, timezone/locale variations,
pagination limits, timeout conditions, re-entrancy and idempotency.
For each requirement produce the 2-3 most important edge cases.
Each test case must include the source_requirement_id matching one of the requirement_ids provided.
Respond ONLY with valid JSON."""

_USER = """\
Generate edge case tests for:

Requirements: {requirements}
Business rules: {rules}
Entities: {entities}

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "EDGE_CASE",
      "title": "string",
      "description": "string (specify the edge condition being targeted)",
      "source_requirement_id": "string",
      "preconditions": ["string"],
      "steps": [{{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}],
      "expected_results": ["string"],
      "test_data": {{}},
      "tags": ["edge-case"]
    }}
  ]
}}"""


class EdgeCaseGeneratorSkill:
    """Generates edge case test cases in a single LLM call for all requirements."""

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        rules: list[dict[str, Any]],
        entities: list[dict[str, Any]],
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
                    entities=json.dumps(entities, indent=2),
                ),
            }],
            tier=ModelTier.BALANCED,
            max_tokens=32768,
        )
        cases = result.get("test_cases", [])
        logger.info("edge_case_generator.complete", test_count=len(cases))
        return cases
