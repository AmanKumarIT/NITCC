"""
NITCC API Gateway — Main Application
Single public-facing FastAPI service exposing all REST endpoints + WebSocket.
PRD Section 11.1 & 11.2
"""

from __future__ import annotations
import asyncio
import logging
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import make_asgi_app, Counter, Histogram

# Shared modules
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.config import settings
from shared.mongodb import connect_db, disconnect_db
from shared.redis_client import connect_redis, disconnect_redis

# Routers
from .routers import (
    trains, tracks, alerts, incidents, weather,
    satellite, cargo, agents_router, reports, auth, websocket_router
)

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "nitcc_gateway_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "nitcc_gateway_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0],
)

# ─────────────────────────────────────────────────────────────────────────────
# Rate Limiting (PRD Section 8.4 — 1000 req/min per key)
# ─────────────────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup/shutdown)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("NITCC Gateway starting up...")
    # Connect databases — graceful degradation if services unavailable
    try:
        await connect_db(settings.mongodb_uri, settings.mongodb_db_name)
        log.info("MongoDB connected")
    except Exception as e:
        log.error(f"MongoDB connection failed (gateway will start without DB): {e}")
    try:
        await connect_redis(settings.redis_url, settings.redis_password)
        log.info("Redis connected")
    except Exception as e:
        log.error(f"Redis connection failed (gateway will start without cache): {e}")
    log.info("NITCC Gateway ready")
    yield
    # Shutdown
    try:
        await disconnect_db()
    except Exception:
        pass
    try:
        await disconnect_redis()
    except Exception:
        pass
    log.info("NITCC Gateway shut down cleanly")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NITCC API Gateway",
    description=(
        "National Intelligent Transportation Command Center — "
        "REST API & WebSocket gateway. OpenAPI 3.0 auto-generated."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS (FR-03.1 — dashboard served from different origin)

print("CORS ORIGINS:", settings.app_cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request Logging + Metrics Middleware
# ─────────────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method, endpoint=request.url.path
    ).observe(duration)

    # Add rate limit headers (PRD Section 11.1)
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Global Error Handler — standard NITCC error envelope (PRD Section 11.1)
# { status, code, message, data }
# ─────────────────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled gateway error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": "Internal server error",
            "data": None,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routers — all versioned at /api/v1/ (PRD Section 11.1)
# ─────────────────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(auth.router,            prefix=f"{PREFIX}/auth",      tags=["Auth"])
app.include_router(trains.router,          prefix=f"{PREFIX}/trains",     tags=["Trains"])
app.include_router(tracks.router,          prefix=f"{PREFIX}/tracks",     tags=["Track Health"])
app.include_router(alerts.router,          prefix=f"{PREFIX}/alerts",     tags=["Alerts"])
app.include_router(incidents.router,       prefix=f"{PREFIX}/incidents",  tags=["Incidents"])
app.include_router(weather.router,         prefix=f"{PREFIX}/weather",    tags=["Weather"])
app.include_router(satellite.router,       prefix=f"{PREFIX}/satellite",  tags=["Satellite"])
app.include_router(cargo.router,           prefix=f"{PREFIX}/cargo",      tags=["Cargo"])
app.include_router(agents_router.router,   prefix=f"{PREFIX}/agents",     tags=["Agents"])
app.include_router(reports.router,         prefix=f"{PREFIX}/reports",    tags=["Reports"])

# WebSocket
app.include_router(websocket_router.router, tags=["WebSocket"])

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "service": "nitcc-gateway",
        "version": "1.0.0",
        "timestamp": time.time(),
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "status": "success",
        "code": 200,
        "message": "NITCC API Gateway v1.0.0 — National Intelligent Transportation Command Center",
        "data": {"docs": "/docs", "health": "/health"},
    }
