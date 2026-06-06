from __future__ import annotations

import json
from typing import Any

import anthropic
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import MODEL_MAP, ModelTier, settings

logger = structlog.get_logger()


class LLMClient:
    """
    Wraps Anthropic client with model routing, retry logic, and structured output support.
    Model selection is driven by task-complexity tier, not hardcoded per skill.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _resolve_model(self, tier: ModelTier | None) -> str:
        return MODEL_MAP[tier or settings.default_model_tier]

    @retry(
        stop=stop_after_attempt(settings.max_skill_retries),
        wait=wait_exponential(multiplier=settings.skill_retry_delay_seconds, max=10),
        reraise=True,
    )
    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tier: ModelTier | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> str:
        model = self._resolve_model(tier)
        log = logger.bind(model=model)
        log.debug("llm.request", message_count=len(messages))

        response = await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content = response.content[0].text
        log.debug("llm.response", output_tokens=response.usage.output_tokens)
        return content

    async def complete_structured(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tier: ModelTier | None = None,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Request JSON output; strip markdown fences and parse."""
        raw = await self.complete(
            system=system,
            messages=messages,
            tier=tier,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)  # type: ignore[no-any-return]


llm_client = LLMClient()
