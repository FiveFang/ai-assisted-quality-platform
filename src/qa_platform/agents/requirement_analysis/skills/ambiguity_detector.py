from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a QA architect reviewing requirements before test planning.
For each requirement, apply this checklist:
1. Is the expected behavior measurable and unambiguous?
2. Are there unstated assumptions a developer might interpret differently?
3. Are there contradictions with other requirements?
4. Are edge cases or error conditions unaddressed?

Flag every issue found. Missing acceptance criteria counts as an ambiguity.
Respond ONLY with valid JSON."""

_USER = """\
Review these requirements for ambiguities:

{requirements}

Business rules for cross-reference:
{rules}

Respond with JSON:
{{
  "ambiguities": [
    {{
      "ambiguity_id": "AMB-001",
      "description": "string (specific, actionable)",
      "severity": "LOW|MEDIUM|HIGH|BLOCKING",
      "affected_requirement": "REQ-XXX",
      "suggested_clarification": "string",
      "blocking": false
    }}
  ]
}}

severity guide:
- BLOCKING: cannot generate valid tests without resolution
- HIGH: likely generates incorrect tests
- MEDIUM: generates incomplete tests
- LOW: minor, tests can proceed with assumptions noted"""


class AmbiguityDetectorSkill:
    """
    Surfaces vague, contradictory, or incomplete requirements before test generation.
    Blocking ambiguities force human escalation regardless of confidence score.
    """

    async def execute(
        self,
        requirements: list[dict[str, Any]],
        rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import json

        logger.info("ambiguity_detector.start", req_count=len(requirements))
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(
                    requirements=json.dumps(requirements, indent=2),
                    rules=json.dumps(rules, indent=2),
                ),
            }],
            tier=ModelTier.BALANCED,
        )
        ambiguities = result.get("ambiguities", [])
        blocking = sum(1 for a in ambiguities if a.get("blocking"))
        logger.info("ambiguity_detector.complete", total=len(ambiguities), blocking=blocking)
        return ambiguities
