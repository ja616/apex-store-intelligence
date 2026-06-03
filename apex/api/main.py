"""FastAPI application entry point.

Features:
  - CORS for React dashboard
  - Prometheus metrics middleware (if enabled)
  - Structured logging with trace IDs
  - Exception handlers returning confidence-aware error responses
  - Lifespan: init DB + warm up models on startup
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apex.config import settings
from apex.models.database import init_db

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Prometheus (optional) ─────────────────────────────────────────────────────
_prometheus_available = False
if settings.enable_prometheus:
    try:
        from prometheus_client import Counter, Histogram, make_asgi_app, REGISTRY
        REQUEST_COUNT = Counter(
            "apex_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
        )
        REQUEST_LATENCY = Histogram(
            "apex_http_request_duration_seconds",
            "HTTP request latency",
            ["method", "endpoint"],
        )
        _prometheus_available = True
    except ImportError:
        logger.warning("prometheus_client not installed — metrics disabled")


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init DB + warm up models.  Shutdown: nothing special."""
    logger.info("APEX Store Intelligence starting up…")

    # Initialise database tables
    try:
        init_db()
        logger.info("Database initialised")
    except Exception as exc:
        logger.error("DB init failed: %s", exc)

    # Warm up ML models (non-blocking: errors are logged, not raised)
    try:
        from apex.pipeline.embeddings import AppearanceEmbedder
        AppearanceEmbedder()
        logger.info("Appearance embedder warmed up")
    except Exception as exc:
        logger.warning("Embedder warmup failed: %s", exc)

    yield   # ← application runs

    logger.info("APEX Store Intelligence shutting down")


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="APEX Store Intelligence",
        description=(
            "Confidence-aware retail analytics platform. "
            "Every metric carries a confidence score and reasoning string."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Trace-ID + latency middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def trace_and_metrics_middleware(request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        t0 = time.perf_counter()

        response: Response = await call_next(request)

        latency = time.perf_counter() - t0
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Response-Time-ms"] = str(round(latency * 1000, 2))

        if _prometheus_available:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
            ).inc()
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(latency)

        logger.debug(
            "trace=%s %s %s → %d (%.1fms)",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            latency * 1000,
        )
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "confidence": 0.0,
                "reasoning": "An unexpected error occurred; metric output unreliable.",
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not found",
                "detail": str(exc),
                "confidence": 0.0,
                "reasoning": "Requested resource does not exist.",
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    from apex.api.routers.events import router as events_router
    from apex.api.routers.stores import router as stores_router
    from apex.api.routers.health import router as health_router
    from apex.api.routers.process import router as process_router

    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(stores_router)
    app.include_router(process_router)

    # ── Prometheus metrics endpoint ───────────────────────────────────────────
    if _prometheus_available:
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

    # ── Root redirect ─────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": "APEX Store Intelligence",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
