from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client
from ....schemas.test_cases import AutomationScaffold, TestCase

logger = structlog.get_logger()

_SYSTEM = """\
You are a test automation engineer. Generate a runnable Python test scaffold for the given test case.
Use Playwright for UI/E2E tests and pytest for API/unit tests.
Follow these conventions:
- Use data-testid selectors for web elements
- Use type hints throughout
- Each test function must be independently executable
- Set up preconditions in the test body or via pytest fixtures
- Use async def for Playwright tests
Respond ONLY with valid JSON."""

_USER = """\
Generate an automation scaffold for this test case:

{test_case}

Respond with JSON:
{{
  "framework": "PLAYWRIGHT|PYTEST|APPIUM",
  "language": "python",
  "scaffold_code": "string (complete, runnable Python test function)",
  "file_path_suggestion": "string (e.g. tests/e2e/cart/test_add_to_cart.py)",
  "imports": ["string"],
  "fixtures_required": ["string"]
}}"""


class ScaffoldGeneratorSkill:
    """
    Generates runnable pytest/Playwright/Appium scaffolds for formatted test cases.
    Only generates scaffolds for non-duplicate P0/P1 cases to control output volume.
    """

    async def execute(self, test_cases: list[TestCase]) -> list[TestCase]:
        import json
        import asyncio

        priority_filter = {"P0", "P1"}
        eligible = [
            (i, tc) for i, tc in enumerate(test_cases)
            if tc.priority in priority_filter and not tc.is_duplicate and tc.automation_scaffold is None
        ]
        logger.info("scaffold_generator.start", eligible=len(eligible))

        if not eligible:
            return test_cases

        async def generate_one(idx: int, tc: TestCase) -> tuple[int, AutomationScaffold | None]:
            try:
                result = await llm_client.complete_structured(
                    system=_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": _USER.format(test_case=json.dumps(tc.model_dump(), indent=2)),
                    }],
                    tier=ModelTier.FAST,
                )
                return idx, AutomationScaffold(**result)
            except Exception as exc:
                logger.warning("scaffold_generator.skip", test_id=tc.test_id, error=str(exc))
                return idx, None

        results = await asyncio.gather(*[generate_one(i, tc) for i, tc in eligible])

        cases = list(test_cases)
        for idx, scaffold in results:
            if scaffold is not None:
                cases[idx] = cases[idx].model_copy(update={"automation_scaffold": scaffold})

        logger.info("scaffold_generator.complete")
        return cases
