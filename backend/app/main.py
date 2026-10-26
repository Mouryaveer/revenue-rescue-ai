"""
RevenueRescue AI — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.DEBUG)
    logger.info("RevenueRescue AI starting", env=settings.APP_ENV, llm_provider=settings.LLM_PROVIDER)
    yield
    logger.info("RevenueRescue AI shutting down")


app = FastAPI(
    title="RevenueRescue AI",
    description="Autonomous AI Revenue Recovery Engine",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return JSONResponse({"status": "ok", "service": "revenuerescue-ai", "version": "0.1.0"})


@app.get("/ready", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def readiness_check():
    from app.services.ml_scoring_service import MLScoringService
    ml_service = MLScoringService()

    db_ok = False
    try:
        from sqlalchemy import text
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    return JSONResponse({
        "status": "ready" if ml_service.is_trained else "degraded_fallback",
        "service": "revenuerescue-ai",
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "database_connected": db_ok,
        "ml_scoring": {
            "is_trained": ml_service.is_trained,
            "model_version": ml_service.model_version,
            "scoring_mode": "lightgbm_tabular" if ml_service.is_trained else "deterministic_heuristic_fallback",
        },
        "reasoning": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.REASONING_MODEL if settings.LLM_PROVIDER in ("cloudflare", "cloudflare_workers_ai") else settings.OPENAI_MODEL,
            "zero_cost_eligible": settings.LLM_PROVIDER in ("deterministic", "mock", "cloudflare", "cloudflare_workers_ai"),
        },
        "safety": {
            "payment_mode": settings.PAYMENT_MODE,
            "allow_real_payments": settings.ALLOW_REAL_PAYMENTS,
            "real_financial_transactions_blocked": not settings.ALLOW_REAL_PAYMENTS,
        },
    })
