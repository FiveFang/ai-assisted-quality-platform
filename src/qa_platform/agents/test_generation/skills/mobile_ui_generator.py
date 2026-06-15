from __future__ import annotations

import asyncio
from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_PLAN_SYSTEM = """\
You are a QA engineer specializing in UI and mobile test automation.
List test scenarios covering the given workflows and UI requirements.
Each scenario maps to one test case with page interactions.
Respond ONLY with valid JSON."""

_PLAN_USER = """\
List UI/mobile test scenarios for:

Workflows: {workflows}
Requirements tagged UI/mobile: {ui_requirements}

Respond with JSON: {{"scenarios": [{{"title": "string", "workflow": "string", "framework": "PLAYWRIGHT|APPIUM"}}]}}"""

_GEN_SYSTEM = """\
You are a QA engineer writing a single UI/mobile test case.
Use data-testid selectors for web (Playwright) and accessibility IDs for mobile (Appium).
Generate a Page Object Model stub in the scaffold. Respond ONLY with valid JSON."""

_GEN_USER = """\
Generate one complete UI/mobile test case.

Title: {title}
Workflow: {workflow}
Framework: {framework}
Workflows context: {workflows}
UI requirements: {ui_requirements}

Respond with JSON:
{{
  "test_case": {{
    "type": "UI",
    "title": "string",
    "description": "string",
    "preconditions": ["string"],
    "steps": [
      {{
        "step_number": 1,
        "action": "string (use data-testid selectors for web, accessibility IDs for mobile)",
        "expected_result": "string",
        "test_data": {{}}
      }}
    ],
    "expected_results": ["string"],
    "automation_scaffold": {{
      "framework": "{framework}",
      "language": "python",
      "scaffold_code": "string (valid Python test function)",
      "file_path_suggestion": "string",
      "imports": ["string"],
      "fixtures_required": ["string"]
    }},
    "tags": ["ui", "e2e"]
  }}
}}"""


class MobileUIGeneratorSkill:
    """Generates UI/mobile test cases one at a time — no bulk JSON."""

    async def execute(
        self,
        workflows: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        ui_reqs = [
            r for r in requirements
            if any(tag in r.get("tags", []) for tag in ("ui", "mobile", "frontend"))
        ]
        if not ui_reqs and not workflows:
            return []

        logger.info("mobile_ui_generator.start", workflow_count=len(workflows))

        workflows_ctx = json.dumps(workflows, indent=2)
        ui_reqs_ctx = json.dumps(ui_reqs, indent=2)

        plan = await llm_client.complete_structured(
            system=_PLAN_SYSTEM,
            messages=[{
                "role": "user",
                "content": _PLAN_USER.format(
                    workflows=workflows_ctx,
                    ui_requirements=ui_reqs_ctx,
                ),
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
                            workflow=scenario.get("workflow", ""),
                            framework=scenario.get("framework", "PLAYWRIGHT"),
                            workflows=workflows_ctx,
                            ui_requirements=ui_reqs_ctx,
                        ),
                    }],
                    tier=ModelTier.BALANCED,
                )
                return result.get("test_case")
            except Exception as exc:
                logger.warning("mobile_ui_generator.gen_one.failed", title=scenario.get("title"), error=str(exc))
                return None

        results = await asyncio.gather(*[gen_one(s) for s in scenarios])
        cases = [r for r in results if r]
        logger.info("mobile_ui_generator.complete", test_count=len(cases))
        return cases
