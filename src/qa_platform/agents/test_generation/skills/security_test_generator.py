from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_PLAN_SYSTEM = """\
You are a security-focused QA engineer. List security test scenarios to VERIFY that defenses work.
Focus on OWASP Top 10 controls: authentication, authorization, input validation, IDOR,
sensitive data exposure, rate limiting, and brute force protection.
Each scenario becomes one test case asserting that a defense works correctly.
Respond ONLY with valid JSON."""

_PLAN_USER = """\
List security test scenarios for:

Requirements: {requirements}
API contracts: {api_contracts}
Entities: {entities}

Respond with JSON: {{"scenarios": [{{"title": "string", "owasp_control": "string", "attack_vector": "string"}}]}}"""

_GEN_SYSTEM = """\
You are a security QA engineer writing a single defensive security test case.
The test VERIFIES that a security control works — it asserts the system correctly rejects or handles
the described attack-like input. Not an attack tool — a verification test.
Respond ONLY with valid JSON."""

_GEN_USER = """\
Generate one complete security test case.

Title: {title}
OWASP control: {owasp_control}
Attack vector being defended against: {attack_vector}
Requirements: {requirements}
API contracts: {api_contracts}

Respond with JSON:
{{
  "test_case": {{
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
}}"""


class SecurityTestGeneratorSkill:
    """Generates defensive security test cases one at a time — no bulk JSON."""

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        api_contracts: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        logger.info("security_test_generator.start")

        plan = await llm_client.complete_structured(
            system=_PLAN_SYSTEM,
            messages=[{
                "role": "user",
                "content": _PLAN_USER.format(
                    requirements=json.dumps(requirements, indent=2),
                    api_contracts=json.dumps(api_contracts, indent=2),
                    entities=json.dumps(entities, indent=2),
                ),
            }],
            tier=ModelTier.FAST,
        )
        scenarios = plan.get("scenarios", [])
        if not scenarios:
            return []

        reqs_ctx = json.dumps(requirements, indent=2)
        contracts_ctx = json.dumps(api_contracts, indent=2)

        async def gen_one(scenario: dict[str, Any]) -> dict[str, Any] | None:
            try:
                result = await llm_client.complete_structured(
                    system=_GEN_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": _GEN_USER.format(
                            title=scenario.get("title", ""),
                            owasp_control=scenario.get("owasp_control", ""),
                            attack_vector=scenario.get("attack_vector", ""),
                            requirements=reqs_ctx,
                            api_contracts=contracts_ctx,
                        ),
                    }],
                    tier=ModelTier.BALANCED,
                )
                return result.get("test_case")
            except Exception as exc:
                logger.warning("security_test_generator.gen_one.failed", title=scenario.get("title"), error=str(exc))
                return None

        results = await asyncio.gather(*[gen_one(s) for s in scenarios])
        cases = [r for r in results if r]
        logger.info("security_test_generator.complete", test_count=len(cases))
        return cases
