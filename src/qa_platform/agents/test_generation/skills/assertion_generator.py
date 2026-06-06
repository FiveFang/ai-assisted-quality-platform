from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA automation engineer. Convert human-readable test expectations into typed,
automation-ready assertion objects. Each assertion must be precise and independently verifiable.

Assertion types: STATUS_CODE, RESPONSE_BODY, DATABASE, UI_ELEMENT, RESPONSE_TIME_MS
Operators: EQUALS, CONTAINS, MATCHES_SCHEMA, IS_NOT_NULL, LESS_THAN, GREATER_THAN

Respond ONLY with valid JSON."""

_USER = """\
Enrich these test cases with typed assertions based on their expected_results:

Test cases:
{test_cases}

For each test case, return the same test_case with an enriched "assertions" array.
Respond with JSON:
{{
  "test_cases": [
    {{
      "test_id_or_index": 0,
      "assertions": [
        {{
          "description": "string",
          "assertion_type": "STATUS_CODE|RESPONSE_BODY|UI_ELEMENT|RESPONSE_TIME_MS",
          "expected_value": "value (string|number|boolean)",
          "operator": "EQUALS|CONTAINS|MATCHES_SCHEMA|IS_NOT_NULL|LESS_THAN"
        }}
      ]
    }}
  ]
}}"""


class AssertionGeneratorSkill:
    """
    Post-processes all test cases to enrich them with typed assertion objects.
    Converts "response contains order ID" → structured assertion with type and operator.
    """

    async def execute(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json

        if not test_cases:
            return test_cases

        logger.info("assertion_generator.start", test_count=len(test_cases))

        # Process in batches of 20 to stay within token limits
        batch_size = 20
        enriched: list[dict[str, Any]] = []

        for i in range(0, len(test_cases), batch_size):
            batch = test_cases[i : i + batch_size]
            indexed = [{"index": j, **tc} for j, tc in enumerate(batch)]

            result = await llm_client.complete_structured(
                system=_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": _USER.format(test_cases=json.dumps(indexed, indent=2)),
                }],
                tier=ModelTier.FAST,
            )

            assertion_map = {
                item["test_id_or_index"]: item["assertions"]
                for item in result.get("test_cases", [])
            }
            for j, tc in enumerate(batch):
                tc_copy = dict(tc)
                if j in assertion_map:
                    tc_copy["assertions"] = assertion_map[j]
                enriched.append(tc_copy)

        logger.info("assertion_generator.complete", test_count=len(enriched))
        return enriched
