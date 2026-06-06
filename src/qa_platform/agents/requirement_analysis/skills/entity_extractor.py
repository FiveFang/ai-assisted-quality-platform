from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are a domain modeling expert. Extract all entities, data models, and external service dependencies
from the provided requirements. Entities become test data factories; dependencies become mock targets.
Respond ONLY with valid JSON."""

_USER = """\
Extract entities and dependencies from:

{artifacts}

Respond with JSON:
{{
  "entities": [
    {{
      "name": "string",
      "type": "USER|SERVICE|DATA_MODEL|EXTERNAL_SYSTEM",
      "attributes": ["string"],
      "description": "string"
    }}
  ],
  "dependencies": [
    {{
      "dependency_id": "DEP-001",
      "name": "string",
      "type": "API|DATABASE|SERVICE|LIBRARY",
      "version": "string or null",
      "criticality": "REQUIRED|OPTIONAL"
    }}
  ]
}}"""


class EntityExtractorSkill:
    """Identifies domain entities and external dependencies for test data and mock planning."""

    async def execute(self, artifacts: dict[str, Any]) -> dict[str, Any]:
        import json

        logger.info("entity_extractor.start")
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": _USER.format(artifacts=json.dumps(artifacts, indent=2)),
            }],
            tier=ModelTier.BALANCED,
        )
        logger.info(
            "entity_extractor.complete",
            entity_count=len(result.get("entities", [])),
            dep_count=len(result.get("dependencies", [])),
        )
        return result
