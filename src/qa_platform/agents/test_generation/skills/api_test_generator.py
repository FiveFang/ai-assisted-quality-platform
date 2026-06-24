from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA engineer specializing in API contract testing.
Generate test cases covering: happy path, documented error codes, auth/authz, schema validation, edge cases.
Each test case must include precise HTTP details: method, path, headers, body, expected status, and response assertions.
Respond ONLY with valid JSON."""

_USER = """\
Generate API test cases for:

Endpoints: {api_contracts}

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "API",
      "title": "string",
      "description": "string",
      "source_requirement_id": "string (endpoint id or empty string if none)",
      "preconditions": ["string"],
      "steps": [
        {{
          "step_number": 1,
          "action": "string (HTTP method + path + headers/body description)",
          "expected_result": "string",
          "test_data": {{}}
        }}
      ],
      "expected_results": ["string"],
      "assertions": [
        {{
          "description": "string",
          "assertion_type": "STATUS_CODE|RESPONSE_BODY|RESPONSE_TIME_MS",
          "expected_value": "value",
          "operator": "EQUALS|CONTAINS|MATCHES_SCHEMA|LESS_THAN"
        }}
      ],
      "tags": ["api"]
    }}
  ]
}}"""


class APITestGeneratorSkill:
    """Generates API test cases in a single LLM call across all endpoints."""

    async def execute(self, api_contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json

        if not api_contracts:
            logger.info("api_test_generator.skipped", reason="no endpoints")
            return []

        logger.info("api_test_generator.start", endpoint_count=len(api_contracts))

        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    api_contracts=json.dumps(api_contracts, indent=2),
                ),
            }],
            tier=ModelTier.BALANCED,
            max_tokens=32768,
        )
        cases = result.get("test_cases", [])
        logger.info("api_test_generator.complete", test_count=len(cases))
        return cases
