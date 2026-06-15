from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_PLAN_SYSTEM = """\
You are a QA engineer. List positive (happy-path) test scenarios for the given requirement.
Each scenario becomes one test case. Respond ONLY with valid JSON."""

_PLAN_USER = """\
List positive test scenarios for:

Requirement: {requirement}
Business rules: {rules}

Respond with JSON: {{"scenarios": [{{"title": "string", "focus": "string"}}]}}"""

_GEN_SYSTEM = """\
You are a QA engineer writing a single detailed test case.
Be specific: concrete actions, exact expected results, realistic test data.
Respond ONLY with valid JSON."""

_GEN_USER = """\
Generate one complete positive test case.

Title: {title}
Focus: {focus}
Requirement: {requirement}
Business rules: {rules}

Respond with JSON:
{{
  "test_case": {{
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
}}"""


class PositiveScenarioSkill:
    """Generates positive (happy-path) test cases one at a time — no bulk JSON."""

    async def execute(
        self,
        requirement: dict[str, Any],
        rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        plan = await llm_client.complete_structured(
            system=_PLAN_SYSTEM,
            messages=[{
                "role": "user",
                "content": _PLAN_USER.format(
                    requirement=json.dumps(requirement, indent=2),
                    rules=json.dumps(rules, indent=2),
                ),
            }],
            tier=ModelTier.FAST,
        )
        scenarios = plan.get("scenarios", [])
        if not scenarios:
            return []

        req_ctx = json.dumps(requirement, indent=2)
        rules_ctx = json.dumps(rules, indent=2)
        req_id = requirement.get("requirement_id", "")

        async def gen_one(scenario: dict[str, Any]) -> dict[str, Any] | None:
            try:
                result = await llm_client.complete_structured(
                    system=_GEN_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": _GEN_USER.format(
                            title=scenario.get("title", ""),
                            focus=scenario.get("focus", ""),
                            requirement=req_ctx,
                            rules=rules_ctx,
                        ),
                    }],
                    tier=ModelTier.BALANCED,
                )
                tc = result.get("test_case")
                if tc:
                    tc["source_requirement_id"] = req_id
                return tc
            except Exception as exc:
                logger.warning("positive_scenario.gen_one.failed", title=scenario.get("title"), error=str(exc))
                return None

        results = await asyncio.gather(*[gen_one(s) for s in scenarios])
        return [r for r in results if r]
