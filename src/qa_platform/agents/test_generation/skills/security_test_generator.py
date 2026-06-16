from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a security QA engineer. Generate security test cases that VERIFY defenses work.
Focus on OWASP Top 10: authentication, authorization, input validation, IDOR,
sensitive data exposure, rate limiting, and brute force protection.
Each test asserts that a security control is in place and correctly rejects the described input.
Each test case must include the source_requirement_id matching one of the requirement_ids provided.
Respond ONLY with valid JSON."""

_USER = """\
Generate security test cases for:

Requirements: {requirements}
API contracts: {api_contracts}
Entities: {entities}

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "SECURITY",
      "title": "string",
      "description": "string (name the OWASP control being verified)",
      "source_requirement_id": "string",
      "preconditions": ["string"],
      "steps": [{{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}],
      "expected_results": ["string (describe expected rejection/defense behavior)"],
      "assertions": [
        {{
          "description": "string",
          "assertion_type": "STATUS_CODE|RESPONSE_BODY",
          "expected_value": "value",
          "operator": "EQUALS|CONTAINS"
        }}
      ],
      "tags": ["security"]
    }}
  ]
}}"""


class SecurityTestGeneratorSkill:
    """Generates security test cases in a single LLM call across all requirements."""

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        api_contracts: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        logger.info("security_test_generator.start")

        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    requirements=json.dumps(requirements, indent=2),
                    api_contracts=json.dumps(api_contracts, indent=2),
                    entities=json.dumps(entities, indent=2),
                ),
            }],
            tier=ModelTier.BALANCED,
            max_tokens=32768,
        )
        cases = result.get("test_cases", [])
        logger.info("security_test_generator.complete", test_count=len(cases))
        return cases
