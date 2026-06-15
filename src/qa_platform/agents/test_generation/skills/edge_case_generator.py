from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_PLAN_SYSTEM = """\
You are a senior QA architect specializing in edge case discovery. List edge cases to test:
- Boundary values (min, max, min±1, max±1)
- Concurrent/parallel operations on the same resource
- Timezone, locale, and character encoding variations
- Pagination boundaries and empty result sets
- Long-running operations and timeout conditions
- Re-entrancy and idempotency (retry same operation twice)

Each scenario becomes one test case. Respond ONLY with valid JSON."""

_PLAN_USER = """\
List edge case scenarios for:

Requirement: {requirement}
Business rules: {rules}
Relevant entities: {entities}

Respond with JSON: {{"scenarios": [{{"title": "string", "edge_condition": "string", "focus": "string"}}]}}"""

_GEN_SYSTEM = """\
You are a QA engineer writing a single edge case test case.
Be precise about the boundary or unusual condition being tested and the expected system behavior.
Respond ONLY with valid JSON."""

_GEN_USER = """\
Generate one complete edge case test case.

Title: {title}
Edge condition: {edge_condition}
Focus: {focus}
Requirement: {requirement}
Business rules: {rules}
Entities: {entities}

Respond with JSON:
{{
  "test_case": {{
    "type": "EDGE_CASE",
    "title": "string",
    "description": "string (specify which edge condition this targets)",
    "preconditions": ["string"],
    "steps": [
      {{"step_number": 1, "action": "string", "expected_result": "string", "test_data": {{}}}}
    ],
    "expected_results": ["string"],
    "test_data": {{}},
    "tags": ["edge-case"]
  }}
}}"""


class EdgeCaseGeneratorSkill:
    """Generates boundary and unusual-condition test cases one at a time — no bulk JSON."""

    async def execute(
        self,
        requirement: dict[str, Any],
        rules: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        plan = await llm_client.complete_structured(
            system=_PLAN_SYSTEM,
            messages=[{
                "role": "user",
                "content": _PLAN_USER.format(
                    requirement=json.dumps(requirement, indent=2),
                    rules=json.dumps(rules, indent=2),
                    entities=json.dumps(entities, indent=2),
                ),
            }],
            tier=ModelTier.FAST,
        )
        scenarios = plan.get("scenarios", [])
        if not scenarios:
            return []

        req_ctx = json.dumps(requirement, indent=2)
        rules_ctx = json.dumps(rules, indent=2)
        entities_ctx = json.dumps(entities, indent=2)
        req_id = requirement.get("requirement_id", "")

        async def gen_one(scenario: dict[str, Any]) -> dict[str, Any] | None:
            try:
                result = await llm_client.complete_structured(
                    system=_GEN_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": _GEN_USER.format(
                            title=scenario.get("title", ""),
                            edge_condition=scenario.get("edge_condition", ""),
                            focus=scenario.get("focus", ""),
                            requirement=req_ctx,
                            rules=rules_ctx,
                            entities=entities_ctx,
                        ),
                    }],
                    tier=ModelTier.BALANCED,
                )
                tc = result.get("test_case")
                if tc:
                    tc["source_requirement_id"] = req_id
                return tc
            except Exception as exc:
                logger.warning("edge_case_generator.gen_one.failed", title=scenario.get("title"), error=str(exc))
                return None

        results = await asyncio.gather(*[gen_one(s) for s in scenarios])
        return [r for r in results if r]
