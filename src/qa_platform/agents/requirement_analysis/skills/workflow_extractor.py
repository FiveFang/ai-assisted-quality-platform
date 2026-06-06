from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a senior systems analyst. Extract user workflows and operational flows from requirements.
Model each workflow as an ordered sequence of steps with actors, preconditions, and postconditions.
Include both the happy path and exception paths.
Respond ONLY with valid JSON."""

_USER = """\
Extract workflows from these requirements:

{requirements}

Respond with JSON:
{{
  "workflows": [
    {{
      "workflow_id": "WF-001",
      "name": "string",
      "description": "string",
      "steps": [
        {{
          "step_id": "S1",
          "action": "string",
          "actor": "string (User|System|ExternalService)",
          "preconditions": ["string"],
          "postconditions": ["string"],
          "alternatives": ["string"]
        }}
      ],
      "happy_path": ["S1", "S2"],
      "exception_paths": [["S1", "S2-error"]]
    }}
  ]
}}"""


class WorkflowExtractorSkill:
    """Extracts user journeys as step-sequenced workflows — the skeleton for E2E test generation."""

    async def execute(self, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json

        logger.info("workflow_extractor.start", req_count=len(requirements))
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(requirements=json.dumps(requirements, indent=2)),
            }],
            tier=ModelTier.BALANCED,
        )
        workflows = result.get("workflows", [])
        logger.info("workflow_extractor.complete", workflow_count=len(workflows))
        return workflows
