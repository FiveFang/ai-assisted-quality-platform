from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .routes import requirements, tests
from ..infrastructure.vector_store import vector_store

logger = structlog.get_logger()

app = FastAPI(
    title="QA Platform",
    version="0.1.0",
    description="AI-assisted QA platform — requirement analysis and test generation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(requirements.router, prefix="/api/v1/requirements", tags=["requirements"])
app.include_router(tests.router, prefix="/api/v1/tests", tags=["tests"])

FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup() -> None:
    try:
        await vector_store.ensure_collection()
    except Exception as exc:
        logger.warning("vector_store.unavailable", error=str(exc),
                       detail="RAG enrichment will be skipped until Postgres is available")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
