from enum import Enum
from pydantic import Field
from pydantic_settings import BaseSettings


class ModelTier(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"


MODEL_MAP: dict[ModelTier, str] = {
    ModelTier.FAST: "claude-haiku-4-5-20251001",
    ModelTier.BALANCED: "claude-sonnet-4-6",
    ModelTier.POWERFUL: "claude-opus-4-8",
}


class Settings(BaseSettings):
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    default_model_tier: ModelTier = ModelTier.BALANCED

    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="qa_platform_requirements", alias="QDRANT_COLLECTION")

    temporal_host: str = Field(default="localhost:7233", alias="TEMPORAL_HOST")
    temporal_namespace: str = Field(default="qa-platform", alias="TEMPORAL_NAMESPACE")

    min_confidence_for_auto_proceed: float = 0.75
    max_ambiguities_for_auto_proceed: int = 3

    max_skill_retries: int = 3
    skill_retry_delay_seconds: float = 1.0

    embedding_model: str = "all-MiniLM-L6-v2"

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
