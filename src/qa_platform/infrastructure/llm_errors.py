"""
Provider-agnostic LLM exceptions.

Each provider adapter catches its SDK-specific errors and re-raises one of these,
so application code (API routes, agents) can handle failures uniformly without
importing any provider SDK.
"""
from __future__ import annotations


class LLMError(Exception):
    """Base class for all provider-agnostic LLM failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class LLMAuthError(LLMError):
    """Invalid or missing API credentials (provider rejected the key)."""


class LLMRateLimitError(LLMError):
    """Provider rate limit or quota exceeded."""


class LLMBadRequestError(LLMError):
    """Malformed request — bad parameters, context too long, content filtered, etc."""


class LLMTimeoutError(LLMError):
    """Request timed out, was interrupted, or the connection dropped."""


class LLMProviderError(LLMError):
    """Any other provider-side error (5xx or otherwise unclassified)."""
