from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a security-focused QA engineer. Generate test cases to VERIFY that security defenses
are correctly implemented. These are defensive tests — assertions that the system correctly
rejects or handles attack-like inputs, not actual attack tools.

Focus on OWASP Top 10 controls relevant to the requirements:
- Authentication and authorization controls
- Input validation (verify rejection of malformed inputs)
- IDOR / object-level access control
- Sensitive data exposure checks
- Rate limiting / brute force protection

Each test case asserts that a defense WORKS, e.g. "verify 401 is returned on expired JWT".
Respond ONLY with valid JSON."""

_USER = """\
Generate security-focused test cases for:

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
      "preconditions": ["string"],
      "steps": [
        {{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}
      ],
      "expected_results": ["string (must describe expected rejection/defense behavior)"],
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
    """
    Generates defensive security test cases verifying OWASP Top 10 controls.
    Output tests verify that defenses work — not exploit code.
    """

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
            max_tokens=8192,
        )
        cases = result.get("test_cases", [])
        logger.info("security_test_generator.complete", test_count=len(cases))
        return cases
