from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_PLAN_SYSTEM = """\
You are a QA engineer specializing in API contract testing.
List test scenarios for the given endpoint: happy path, documented error codes,
auth/authz, schema validation, and any endpoint-specific edge cases.
Each scenario becomes one test case. Respond ONLY with valid JSON."""

_PLAN_USER = """\
List API test scenarios for this endpoint:

{endpoint}

Respond with JSON: {{"scenarios": [{{"title": "string", "scenario_type": "string", "http_status": "string"}}]}}"""

_GEN_SYSTEM = """\
You are a QA engineer writing a single API test case.
Use precise HTTP details: method, path, headers, request body, expected status, and response assertions.
Respond ONLY with valid JSON."""

_GEN_USER = """\
Generate one complete API test case.

Title: {title}
Scenario type: {scenario_type}
Expected HTTP status: {http_status}
Endpoint: {endpoint}

Respond with JSON:
{{
  "test_case": {{
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
}}"""


class APITestGeneratorSkill:
    """Generates API test cases one at a time per endpoint scenario — no bulk JSON."""

    async def execute(self, api_contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json

        logger.info("api_test_generator.start", endpoint_count=len(api_contracts))

        async def process_endpoint(endpoint: dict[str, Any]) -> list[dict[str, Any]]:
            endpoint_ctx = json.dumps(endpoint, indent=2)

            plan = await llm_client.complete_structured(
                system=_PLAN_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": _PLAN_USER.format(endpoint=endpoint_ctx),
                }],
                tier=ModelTier.FAST,
            )
            scenarios = plan.get("scenarios", [])
            if not scenarios:
                return []

            async def gen_one(scenario: dict[str, Any]) -> dict[str, Any] | None:
                try:
                    result = await llm_client.complete_structured(
                        system=_GEN_SYSTEM,
                        messages=[{
                            "role": "user",
                            "content": _GEN_USER.format(
                                title=scenario.get("title", ""),
                                scenario_type=scenario.get("scenario_type", ""),
                                http_status=scenario.get("http_status", ""),
                                endpoint=endpoint_ctx,
                            ),
                        }],
                        tier=ModelTier.BALANCED,
                    )
                    return result.get("test_case")
                except Exception as exc:
                    logger.warning("api_test_generator.gen_one.failed", title=scenario.get("title"), error=str(exc))
                    return None

            results = await asyncio.gather(*[gen_one(s) for s in scenarios])
            return [r for r in results if r]

        endpoint_results = await asyncio.gather(*[process_endpoint(ep) for ep in api_contracts])
        all_cases: list[dict[str, Any]] = []
        for cases in endpoint_results:
            all_cases.extend(cases)

        logger.info("api_test_generator.complete", test_count=len(all_cases))
        return all_cases
