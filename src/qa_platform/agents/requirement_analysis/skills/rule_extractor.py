from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a skeptical QA architect reviewing requirements before test planning.
Surface ALL business rules — both explicit (stated in requirements) and implicit (implied but unstated).
Implicit rules are equally important: they become test assertions.
Respond ONLY with valid JSON."""

_USER = """\
For each of the following requirements, enumerate every business rule that must hold
for the system to be correct. Think: validation rules, authorization constraints,
computation logic, and invariants.

Requirements:
{requirements}

Respond with JSON:
{{
  "rules": [
    {{
      "rule_id": "BR-001",
      "description": "string",
      "rule_type": "VALIDATION|AUTHORIZATION|COMPUTATION|CONSTRAINT",
      "applies_to": ["entity or requirement ID"],
      "is_explicit": true,
      "confidence": 0.95
    }}
  ]
}}"""


class RuleExtractorSkill:
    """
    Surfaces explicit and implicit business rules.
    is_explicit=false rules flag potential missing acceptance criteria for human review.
    """

    async def execute(self, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json

        logger.info("rule_extractor.start", req_count=len(requirements))
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(requirements=json.dumps(requirements, indent=2)),
            }],
            tier=ModelTier.BALANCED,
        )
        rules = result.get("rules", [])
        logger.info("rule_extractor.complete", rule_count=len(rules))
        return rules
