"""
State management for workflow execution.
Production: Temporal handles durable state via activity inputs/outputs.
Dev/test: in-memory fallback used when Temporal is not available.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class InMemoryStateStore:
    """Not for production use — dev/test only."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        logger.debug("state.set", key=key)

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


state_store = InMemoryStateStore()
