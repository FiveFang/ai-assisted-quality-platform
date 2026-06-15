from __future__ import annotations

import importlib.util

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import LLMProvider, ModelSpec, parse_model_spec, settings

router = APIRouter()

# Which optional SDK each provider needs at runtime (Anthropic ships as a base dep).
_PROVIDER_SDK = {
    LLMProvider.OPENAI: "openai",
    LLMProvider.GEMINI: "google.genai",
}


def _sdk_installed(provider: LLMProvider) -> bool:
    module = _PROVIDER_SDK.get(provider)
    if module is None:
        return True
    return importlib.util.find_spec(module) is not None


class ModelOption(BaseModel):
    spec: str  # "provider:model_id" — pass back as AnalyzeRequest.model
    provider: str
    model_id: str


class ModelsResponse(BaseModel):
    default: str  # the tier-based default label
    options: list[ModelOption]


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """Models the user can select — only those whose provider key is configured."""
    options = [
        ModelOption(spec=str(s), provider=s.provider.value, model_id=s.model_id)
        for s in settings.available_models()
        if _sdk_installed(s.provider)
    ]
    return ModelsResponse(default="Default (tier-based routing)", options=options)


def resolve_model_override(model: str | None) -> ModelSpec | None:
    """
    Validate a user-supplied "provider:model_id" override. Returns None for the
    default (tier-based) routing. Raises HTTPException(400) with an actionable
    message if the provider is unknown, its key is missing, or its SDK isn't installed.
    """
    if not model:
        return None

    try:
        spec = parse_model_spec(model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not settings.has_provider_key(spec.provider):
        env_var = settings.env_var_for_provider(spec.provider)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model '{model}' requires the {spec.provider.value} provider, "
                f"but {env_var} is not configured on the server."
            ),
        )

    if not _sdk_installed(spec.provider):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model '{model}' requires the {spec.provider.value} SDK, "
                f"which is not installed on the server."
            ),
        )

    return spec
