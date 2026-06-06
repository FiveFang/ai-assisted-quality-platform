from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

_P0_TAGS = frozenset({"security", "payment", "auth", "authorization", "data-loss"})
_P1_TAGS = frozenset({"functional", "happy-path", "core"})
_P3_TAGS = frozenset({"cosmetic", "accessibility-minor"})

_P0_TYPES = frozenset({"SECURITY"})
_API_P1_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


class RiskPriorizerSkill:
    """
    Assigns P0–P3 priority to each test case based on type, tags, and content signals.
    Rule-based; LLM is not needed for the majority of cases.

    P0: Security, payment, auth/authz, data loss
    P1: Happy path for core journeys, API write operations
    P2: Negative scenarios, read operations, non-critical edge cases
    P3: Nice-to-have coverage, cosmetic assertions
    """

    async def execute(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        logger.info("risk_prioritizer.start", test_count=len(test_cases))

        for tc in test_cases:
            tc["priority"] = self._assign_priority(tc)
            tc["risk_score"] = self._compute_risk_score(tc)

        by_priority = {}
        for tc in test_cases:
            p = tc["priority"]
            by_priority[p] = by_priority.get(p, 0) + 1

        logger.info("risk_prioritizer.complete", by_priority=by_priority)
        return test_cases

    def _assign_priority(self, tc: dict[str, Any]) -> str:
        tc_type = tc.get("type", "")
        tags = set(tc.get("tags", []))
        title_lower = tc.get("title", "").lower()

        if tc_type in _P0_TYPES or tags & _P0_TAGS:
            return "P0"
        if any(kw in title_lower for kw in ("payment", "auth", "login", "security", "password")):
            return "P0"
        if tc_type == "FUNCTIONAL" and "positive" in tags:
            return "P1"
        if tc_type == "API" and any(
            kw in title_lower for kw in ("post", "put", "delete", "patch", "create", "update")
        ):
            return "P1"
        if tc_type in ("NEGATIVE", "EDGE_CASE"):
            return "P2"
        if tags & _P3_TAGS:
            return "P3"
        return "P2"

    def _compute_risk_score(self, tc: dict[str, Any]) -> float:
        priority_map = {"P0": 1.0, "P1": 0.75, "P2": 0.5, "P3": 0.25}
        return priority_map.get(tc.get("priority", "P2"), 0.5)
