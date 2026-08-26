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
    description="AI Revenue Recovery Agent — Razorpay Buildathon Track 03",
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
