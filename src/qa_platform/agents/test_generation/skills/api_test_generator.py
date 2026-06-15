from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA engineer specializing in API contract testing.
For each endpoint, generate: happy path, all documented error codes, auth/authz tests,
and schema validation tests. Use the request/response schemas to generate precise assertions.
Respond ONLY with valid JSON."""

_USER = """\
Generate up to 5 API test cases for this endpoint:

{endpoint}

Respond with JSON:
{{
  "test_cases": [
    {{
      "type": "API",
      "title": "string",
      "description": "string",
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
    """
    Generates test cases from OpenAPI contracts.
    Covers: happy path, all documented error codes, auth/authz, schema validation.
    """

    async def execute(self, api_contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json
        import asyncio

        logger.info("api_test_generator.start", endpoint_count=len(api_contracts))

        tasks = [
            llm_client.complete_structured(
                system=_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": _USER.format(endpoint=json.dumps(endpoint, indent=2)),
                }],
                tier=ModelTier.BALANCED,
            )
            for endpoint in api_contracts
        ]
        results = await asyncio.gather(*tasks)

        all_cases: list[dict[str, Any]] = []
        for result in results:
            all_cases.extend(result.get("test_cases", []))

        logger.info("api_test_generator.complete", test_count=len(all_cases))
        return all_cases
