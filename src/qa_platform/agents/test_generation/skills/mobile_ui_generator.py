from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA engineer specializing in UI and mobile test automation.
Map workflow steps to concrete page interactions. Generate Page Object Model stubs.
For mobile tests use Appium conventions; for web tests use Playwright conventions.
Respond ONLY with valid JSON."""

_USER = """\
Generate UI/mobile test cases from these workflows:

Workflows: {workflows}
Requirements tagged UI/mobile: {ui_requirements}

Respond with JSON:
{{
  "test_cases": [
    {{
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
        "framework": "PLAYWRIGHT|APPIUM",
        "language": "python",
        "scaffold_code": "string (valid Python test function)",
        "file_path_suggestion": "string",
        "imports": ["string"],
        "fixtures_required": ["string"]
      }},
      "tags": ["ui", "e2e"]
    }}
  ]
}}"""


class MobileUIGeneratorSkill:
    """Generates UI/mobile test cases with Playwright or Appium scaffolds from workflow graphs."""

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
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    workflows=json.dumps(workflows, indent=2),
                    ui_requirements=json.dumps(ui_reqs, indent=2),
                ),
            }],
            tier=ModelTier.FAST,
        )
        cases = result.get("test_cases", [])
        logger.info("mobile_ui_generator.complete", test_count=len(cases))
        return cases
