from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are an expert business analyst specializing in requirements engineering.
Parse the provided Product Requirements Document (PRD) and extract structured information.
Respond ONLY with valid JSON. Do not include any explanation outside the JSON structure."""

_USER = """\
Parse the following PRD and extract structured information.

PRD Content:
{prd_content}

Respond with JSON matching this exact structure:
{{
  "product_overview": "string",
  "goals": ["string"],
  "user_personas": [{{"name": "string", "role": "string", "needs": ["string"]}}],
  "features": [
    {{
      "feature_id": "F-001",
      "title": "string",
      "description": "string",
      "acceptance_criteria": ["string"],
      "priority": "P0|P1|P2|P3"
    }}
  ],
  "non_functional_requirements": ["string"],
  "constraints": ["string"],
  "assumptions": ["string"],
  "out_of_scope": ["string"]
}}"""


class PRDParserSkill:
    """Normalizes free-form PRD documents into structured feature/requirement data."""

    async def execute(self, prd_content: str, max_tokens: int | None = None) -> dict[str, Any]:
        logger.info("prd_parser.start", content_length=len(prd_content))
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{"role": "user", "content": _USER.format(prd_content=prd_content)}],
            tier=ModelTier.BALANCED,
            **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        )
        logger.info("prd_parser.complete", feature_count=len(result.get("features", [])))
        return result
