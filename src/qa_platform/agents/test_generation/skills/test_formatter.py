from __future__ import annotations

from typing import Any

import structlog

from ....schemas.test_cases import Assertion, AutomationScaffold, TestCase, TestStep
from pydantic import ValidationError

logger = structlog.get_logger()


class TestFormatterSkill:
    """
    Normalizes all test cases to the canonical TestCase schema.
    Validates via Pydantic; logs and skips cases that fail validation rather than crashing.
    """

    async def execute(self, test_cases: list[dict[str, Any]]) -> list[TestCase]:
        logger.info("test_formatter.start", raw_count=len(test_cases))
        formatted: list[TestCase] = []
        skipped = 0

        for tc in test_cases:
            try:
                formatted.append(self._normalize(tc))
            except (ValidationError, KeyError, TypeError) as exc:
                logger.warning("test_formatter.skip", title=tc.get("title"), error=str(exc))
                skipped += 1

        logger.info("test_formatter.complete", formatted=len(formatted), skipped=skipped)
        return formatted

    def _normalize(self, tc: dict[str, Any]) -> TestCase:
        steps = [
            TestStep(
                step_number=i + 1 if not isinstance(s.get("step_number"), int) else s["step_number"],
                action=s["action"],
                expected_result=s.get("expected_result", ""),
                test_data=s.get("test_data"),
            )
            for i, s in enumerate(tc.get("steps", []))
        ]

        assertions = [
            Assertion(
                description=a.get("description", ""),
                assertion_type=a.get("assertion_type", "RESPONSE_BODY"),
                expected_value=a.get("expected_value"),
                operator=a.get("operator", "EQUALS"),
            )
            for a in tc.get("assertions", [])
        ]

        scaffold_data = tc.get("automation_scaffold")
        scaffold = AutomationScaffold(**scaffold_data) if scaffold_data else None

        return TestCase(
            source_requirement_id=tc.get("source_requirement_id", ""),
            type=tc.get("type", "FUNCTIONAL"),
            priority=tc.get("priority", "P2"),
            title=tc["title"],
            description=tc.get("description", ""),
            preconditions=tc.get("preconditions", []),
            steps=steps,
            expected_results=tc.get("expected_results", []),
            assertions=assertions,
            test_data=tc.get("test_data", {}),
            tags=tc.get("tags", []),
            automation_scaffold=scaffold,
            risk_score=tc.get("risk_score", 0.5),
            is_duplicate=tc.get("is_duplicate", False),
            duplicate_of=tc.get("duplicate_of"),
        )
