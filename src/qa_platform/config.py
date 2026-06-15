from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings


class ModelTier(str, Enum):
    """Task-complexity tier. Skills request a tier; the tier maps to a concrete model."""

    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


@dataclass(frozen=True)
class ModelSpec:
    """A concrete model: which provider serves it, and its provider-specific model id."""

    provider: LLMProvider
    model_id: str

    def __str__(self) -> str:
        return f"{self.provider.value}:{self.model_id}"


def parse_model_spec(spec: str) -> ModelSpec:
    """
    Parse a "provider:model_id" string, e.g. "openai:gpt-4o" or "gemini:gemini-2.0-flash".
    A bare model id (no colon) is assumed to be Anthropic for backwards compatibility.
    """
    if ":" in spec:
        provider_raw, model_id = spec.split(":", 1)
        try:
            provider = LLMProvider(provider_raw.strip().lower())
        except ValueError as exc:
            supported = ", ".join(p.value for p in LLMProvider)
            raise ValueError(
                f"Unknown LLM provider '{provider_raw}'. Supported providers: {supported}"
            ) from exc
        return ModelSpec(provider, model_id.strip())
    return ModelSpec(LLMProvider.ANTHROPIC, spec.strip())


class Settings(BaseSettings):
    # ── Provider credentials — only the provider(s) you actually use need a key ──
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")

    # ── Per-tier model selection, as "provider:model_id" strings ──
    # Swap any tier to another provider without touching code, e.g.
    #   BALANCED_MODEL=openai:gpt-4o   POWERFUL_MODEL=gemini:gemini-2.5-pro
    fast_model: str = Field(default="anthropic:claude-haiku-4-5-20251001", alias="FAST_MODEL")
    balanced_model: str = Field(default="anthropic:claude-sonnet-4-6", alias="BALANCED_MODEL")
    powerful_model: str = Field(default="anthropic:claude-opus-4-8", alias="POWERFUL_MODEL")

    default_model_tier: ModelTier = ModelTier.BALANCED

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/qa_platform",
        alias="DATABASE_URL",
    )
    vector_table: str = Field(default="requirements_embeddings", alias="VECTOR_TABLE")

    temporal_host: str = Field(default="localhost:7233", alias="TEMPORAL_HOST")
    temporal_namespace: str = Field(default="qa-platform", alias="TEMPORAL_NAMESPACE")

    min_confidence_for_auto_proceed: float = 0.75
    max_ambiguities_for_auto_proceed: int = 3

    max_skill_retries: int = 3
    skill_retry_delay_seconds: float = 1.0

    embedding_model: str = "all-MiniLM-L6-v2"

    model_config = {"env_file": ".env", "populate_by_name": True}

    @property
    def model_specs(self) -> dict[ModelTier, ModelSpec]:
        return {
            ModelTier.FAST: parse_model_spec(self.fast_model),
            ModelTier.BALANCED: parse_model_spec(self.balanced_model),
            ModelTier.POWERFUL: parse_model_spec(self.powerful_model),
        }

    def resolve_model(self, tier: ModelTier | None) -> ModelSpec:
        """Resolve a tier (or the default tier) to a concrete ModelSpec."""
        return self.model_specs[tier or self.default_model_tier]

    def has_provider_key(self, provider: LLMProvider) -> bool:
        """Whether an API key is configured for the given provider."""
        key = {
            LLMProvider.ANTHROPIC: self.anthropic_api_key,
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.GEMINI: self.google_api_key,
        }.get(provider)
        return bool(key)

    def env_var_for_provider(self, provider: LLMProvider) -> str:
        """The env var name a user must set to enable the given provider."""
        return {
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.GEMINI: "GOOGLE_API_KEY",
        }[provider]

    def available_models(self) -> list[ModelSpec]:
        """
        Distinct tier-configured models whose provider has a key set.
        Drives the model picker so users only see selectable options.
        """
        seen: set[str] = set()
        result: list[ModelSpec] = []
        for spec in self.model_specs.values():
            if self.has_provider_key(spec.provider) and str(spec) not in seen:
                seen.add(str(spec))
                result.append(spec)
        return result


settings = Settings()
