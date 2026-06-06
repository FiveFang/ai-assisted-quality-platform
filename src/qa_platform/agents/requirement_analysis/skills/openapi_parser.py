from __future__ import annotations

from typing import Any

import prance
import structlog

logger = structlog.get_logger()


class OpenAPIParserSkill:
    """
    Parses OpenAPI 3.x specs into structured API contract definitions.
    Uses prance for deterministic $ref resolution — no LLM needed for parsing.
    """

    async def execute(self, spec_content: str) -> dict[str, Any]:
        logger.info("openapi_parser.start")

        # prance resolves all $ref chains synchronously
        parser = prance.ResolvingParser(spec_string=spec_content, resolve_types=prance.RESOLVE_HTTP)
        spec = parser.specification

        contracts = []
        for path, path_item in spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                contracts.append(self._extract_contract(method.upper(), path, operation))

        logger.info("openapi_parser.complete", endpoint_count=len(contracts))
        return {"api_contracts": contracts}

    def _extract_contract(self, method: str, path: str, operation: dict[str, Any]) -> dict[str, Any]:
        security = operation.get("security", [])
        responses = {
            code: schema.get("content", {})
            for code, schema in operation.get("responses", {}).items()
        }
        request_body = operation.get("requestBody", {})
        request_schema = (
            next(iter(request_body.get("content", {}).values()), {}).get("schema")
            if request_body
            else None
        )

        return {
            "method": method,
            "path": path,
            "summary": operation.get("summary"),
            "auth_required": len(security) > 0,
            "request_schema": request_schema,
            "response_schema": responses,
            "parameters": operation.get("parameters", []),
        }
