from __future__ import annotations

from typing import Any

import structlog

from ....config import ModelTier
from ....infrastructure.llm_client import llm_client

logger = structlog.get_logger()

_SYSTEM = """\
You are an expert QA analyst. Parse the provided Jira stories or user stories into a normalized format.
Detect if the content uses Gherkin (Given/When/Then) and extract accordingly.
Respond ONLY with valid JSON."""

_USER = """\
Parse the following Jira/user story content:

{jira_content}

Respond with JSON:
{{
  "stories": [
    {{
      "id": "string",
      "title": "string",
      "description": "string",
      "given": ["string"],
      "when": ["string"],
      "then": ["string"],
      "acceptance_criteria": ["string"],
      "priority": "P0|P1|P2|P3",
      "linked_issues": ["string"],
      "labels": ["string"]
    }}
  ]
}}"""


class JiraParserSkill:
    """Parses Jira issue exports or Gherkin user stories into normalized story objects."""

    async def execute(self, jira_content: str, max_tokens: int | None = None) -> dict[str, Any]:
        logger.info("jira_parser.start", content_length=len(jira_content))
        result = await llm_client.complete_structured(
            system=_SYSTEM,
            messages=[{"role": "user", "content": _USER.format(jira_content=jira_content)}],
            tier=ModelTier.FAST,
            **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        )
        logger.info("jira_parser.complete", story_count=len(result.get("stories", [])))
        return result
