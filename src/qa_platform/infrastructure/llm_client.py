from __future__ import annotations

import contextvars
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import LLMProvider, ModelSpec, ModelTier, settings
from .llm_errors import (
    LLMAuthError,
    LLMBadRequestError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = structlog.get_logger()

# Read timeout for a single (streamed) LLM call. Generous because we stream —
# streaming keeps the connection alive across long generations, so this only
# trips on a genuinely stuck request, not a slow-but-progressing one.
_REQUEST_TIMEOUT_SECONDS = 300.0

# Request-scoped model override. When set, it supersedes per-skill tier routing for
# the duration of a single analysis/generation run. ContextVar is async-safe: tasks
# spawned via asyncio.gather inherit the value set on the parent request task.
_model_override: contextvars.ContextVar[ModelSpec | None] = contextvars.ContextVar(
    "llm_model_override", default=None
)


@contextmanager
def use_model(spec: ModelSpec | None) -> Iterator[None]:
    """Within this block, force all LLM calls to use `spec` regardless of tier.
    Passing None is a no-op (keeps tier-based routing)."""
    if spec is None:
        yield
        return
    token = _model_override.set(spec)
    try:
        yield
    finally:
        _model_override.reset(token)


class _Provider(Protocol):
    """Common surface every provider adapter implements."""

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model_id: str,
        max_tokens: int,
        json_mode: bool,
    ) -> str: ...


class _AnthropicProvider:
    def __init__(self) -> None:
        import anthropic
        import httpx

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set but an Anthropic model was requested.")
        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=httpx.Timeout(_REQUEST_TIMEOUT_SECONDS, connect=10.0),
            max_retries=0,  # we own retries via tenacity — don't double-retry
        )

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model_id: str,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        a = self._anthropic
        # Stream so the connection stays alive across long generations (avoids
        # read-timeout-then-retry storms on large max_tokens). Anthropic has no
        # native JSON mode; the markdown-strip fallback handles json_mode.
        try:
            async with self._client.messages.stream(
                model=model_id,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
            ) as stream:
                final = await stream.get_final_message()
            return final.content[0].text
        except a.AuthenticationError as exc:
            raise LLMAuthError(str(exc), provider="anthropic", status_code=401) from exc
        except a.RateLimitError as exc:
            raise LLMRateLimitError(str(exc), provider="anthropic", status_code=429) from exc
        except a.BadRequestError as exc:
            raise LLMBadRequestError(
                getattr(exc, "message", str(exc)), provider="anthropic", status_code=400
            ) from exc
        except (a.APITimeoutError, a.APIConnectionError) as exc:
            raise LLMTimeoutError(str(exc), provider="anthropic") from exc
        except a.APIStatusError as exc:
            raise LLMProviderError(
                getattr(exc, "message", str(exc)),
                provider="anthropic",
                status_code=getattr(exc, "status_code", None),
            ) from exc


class _OpenAIProvider:
    def __init__(self) -> None:
        try:
            import openai
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "OpenAI provider requires the 'openai' package. "
                "Install with: pip install 'qa-platform[openai]'"
            ) from exc

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set but an OpenAI model was requested.")
        self._openai = openai
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model_id: str,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        o = self._openai
        kwargs: dict[str, Any] = {}
        if json_mode:
            # JSON mode requires the word "json" somewhere in the prompt.
            if "json" not in system.lower():
                system = system + "\n\nRespond with a single valid JSON object."
            kwargs["response_format"] = {"type": "json_object"}
        try:
            # Stream and accumulate so long generations don't hit the read timeout.
            stream = await self._client.chat.completions.create(
                model=model_id,
                messages=[{"role": "system", "content": system}, *messages],
                max_completion_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
            parts: list[str] = []
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    parts.append(delta)
            return "".join(parts)
        except o.AuthenticationError as exc:
            raise LLMAuthError(str(exc), provider="openai", status_code=401) from exc
        except o.RateLimitError as exc:
            raise LLMRateLimitError(str(exc), provider="openai", status_code=429) from exc
        except o.BadRequestError as exc:
            raise LLMBadRequestError(str(exc), provider="openai", status_code=400) from exc
        except (o.APITimeoutError, o.APIConnectionError) as exc:
            raise LLMTimeoutError(str(exc), provider="openai") from exc
        except o.APIStatusError as exc:
            raise LLMProviderError(
                str(exc), provider="openai", status_code=getattr(exc, "status_code", None)
            ) from exc


class _GeminiProvider:
    def __init__(self) -> None:
        try:
            from google import genai
            from google.genai import errors as genai_errors
        except ImportError as exc:
            raise ImportError(
                "Gemini provider requires the 'google-genai' package. "
                "Install with: pip install 'qa-platform[gemini]'"
            ) from exc

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set but a Gemini model was requested.")
        self._errors = genai_errors
        self._client = genai.Client(
            api_key=settings.google_api_key,
            http_options={"timeout": int(_REQUEST_TIMEOUT_SECONDS * 1000)},  # ms
        )

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model_id: str,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        from google.genai import types

        # Gemini uses 'model' for assistant turns and a 'parts' content shape.
        contents = [
            types.Content(
                role="model" if m.get("role") == "assistant" else "user",
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
        )
        try:
            # Stream and accumulate so long generations don't hit the read timeout.
            parts: list[str] = []
            async for chunk in await self._client.aio.models.generate_content_stream(
                model=model_id,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    parts.append(chunk.text)
            return "".join(parts)
        except self._errors.APIError as exc:
            code = getattr(exc, "code", None)
            msg = getattr(exc, "message", str(exc))
            if code in (401, 403):
                raise LLMAuthError(msg, provider="gemini", status_code=code) from exc
            if code == 429:
                raise LLMRateLimitError(msg, provider="gemini", status_code=code) from exc
            if isinstance(code, int) and 400 <= code < 500:
                raise LLMBadRequestError(msg, provider="gemini", status_code=code) from exc
            raise LLMProviderError(msg, provider="gemini", status_code=code) from exc


class LLMClient:
    """
    Provider-agnostic LLM wrapper with tier-based model routing, retries, and
    structured (JSON) output. Each tier resolves to a "provider:model_id" spec from
    settings, so models can be swapped — across providers — via env vars alone.

    All providers stream internally (keeping the connection alive across long
    generations) and have their SDK-level auto-retry disabled — retries are owned
    here by tenacity, so there's a single retry layer. Provider clients are created
    lazily on first use; failures are normalized to the exceptions in llm_errors.
    """

    def __init__(self) -> None:
        self._providers: dict[LLMProvider, _Provider] = {}
        self._factories: dict[LLMProvider, type[_Provider]] = {
            LLMProvider.ANTHROPIC: _AnthropicProvider,
            LLMProvider.OPENAI: _OpenAIProvider,
            LLMProvider.GEMINI: _GeminiProvider,
        }

    def _try_repair_json(self, raw: str) -> str | None:
        """
        Attempt to salvage truncated/malformed JSON by finding the last complete
        object or array. Looks backwards from the end to find matching braces.
        """
        # Try to find a complete JSON object {} or array []
        for end_pos in range(len(raw) - 1, max(0, len(raw) - 1000), -1):
            if raw[end_pos] in ('}', ']'):
                # Try to parse from start to this position
                candidate = raw[:end_pos + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue
        return None

    def _get_provider(self, provider: LLMProvider) -> _Provider:
        if provider not in self._providers:
            self._providers[provider] = self._factories[provider]()
        return self._providers[provider]

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
        max_tokens: int = 8192,
        json_mode: bool = False,
    ) -> str:
        spec = _model_override.get() or settings.resolve_model(tier)
        provider = self._get_provider(spec.provider)
        log = logger.bind(provider=spec.provider.value, model=spec.model_id)
        log.debug("llm.request", message_count=len(messages), json_mode=json_mode)

        content = await provider.complete(system, messages, spec.model_id, max_tokens, json_mode)

        log.debug("llm.response", output_length=len(content))
        return content

    async def complete_structured(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tier: ModelTier | None = None,
        max_tokens: int = 16384,
    ) -> dict[str, Any]:
        """Request JSON output. Providers with native JSON mode use it; the
        markdown-fence strip below remains a safety net for all providers."""
        raw = await self.complete(
            system=system,
            messages=messages,
            tier=tier,
            max_tokens=max_tokens,
            json_mode=True,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except json.JSONDecodeError as exc:
            # Log the error location and a sample of the malformed JSON
            error_line = exc.lineno or 1
            error_col = exc.colno or 1
            error_pos = exc.pos or 0

            # Extract a window around the error for debugging
            window_start = max(0, error_pos - 200)
            window_end = min(len(raw), error_pos + 200)
            error_context = raw[window_start:window_end]

            logger.error(
                "llm.json_parse_error",
                error=str(exc),
                raw_length=len(raw),
                error_line=error_line,
                error_col=error_col,
                error_pos=error_pos,
                error_context=error_context,
            )

            # Try to salvage what we can: find the last complete JSON object/array
            repaired = self._try_repair_json(raw)
            if repaired is not None:
                logger.info("llm.json_repaired", original_length=len(raw), repaired_length=len(repaired))
                try:
                    return json.loads(repaired)  # type: ignore[no-any-return]
                except json.JSONDecodeError:
                    pass  # Fall through to the error below

            raise ValueError(f"AI returned malformed JSON (output may have been truncated): {exc}") from exc


llm_client = LLMClient()
