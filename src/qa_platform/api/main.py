from __future__ import annotations

import os

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .routes import meta, requirements, tests
from ..infrastructure.review_store import review_store
from ..infrastructure.state_store import state_store
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
app.include_router(meta.router, prefix="/api/v1", tags=["meta"])

FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup() -> None:
    try:
        await state_store.upgrade_to_postgres()
        await review_store.upgrade_to_postgres()
    except Exception as exc:
        logger.warning(
            "state_store.postgres_unavailable",
            error=str(exc),
            detail="Results will not persist across restarts (in-memory fallback active)",
        )

    try:
        await vector_store.ensure_collection()
    except Exception as exc:
        logger.warning("vector_store.unavailable", error=str(exc),
                       detail="RAG enrichment will be skipped until Postgres is available")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the pre-built React frontend when running in Docker / production.
# Must come AFTER all API routes so /api/v1/... is never shadowed.
_frontend_dist = os.environ.get("FRONTEND_DIST_DIR", "frontend/dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
