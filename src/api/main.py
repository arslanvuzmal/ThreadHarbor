from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import redis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.analytics.db import async_engine, init_db
from src.api.routes import agent_webhook, webhook
from src.bot.session import SessionManager
from src.intelligence.tracing import get_tracing_manager
from src.utils.config import get_settings
from src.utils.logger import configure_logger, get_logger

# Load initial settings and configure logger
settings = get_settings()
configure_logger(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler for FastAPI application setup and teardown tasks."""
    # Application startup tasks
    await init_db()

    yield

    # Application shutdown tasks - Graceful Shutdown & Signal Handling
    # Uvicorn by default registers signal handlers for SIGTERM and SIGINT,
    # and will gracefully initiate the FastAPI lifespan shutdown events/lifespan teardown.
    logger.info("Initiating graceful shutdown...")

    # Close Redis connections
    try:
        SessionManager._store_instance.close()
    except Exception as e:
        logger.error("Failed to close Redis connection during shutdown", error=str(e))

    # Flush Langfuse traces
    try:
        manager = get_tracing_manager()
        if manager.enabled and manager.langfuse:
            manager.langfuse.flush()
            logger.info("Flushed Langfuse traces gracefully")
    except Exception as e:
        logger.error("Failed to flush Langfuse traces on shutdown", error=str(e))

    logger.info("Graceful shutdown completed successfully")


app = FastAPI(
    title="WhatsApp Support Bot API",
    version="0.1.0",
    docs_url="/docs" if settings.LOG_LEVEL == "DEBUG" else None,
    redoc_url="/redoc" if settings.LOG_LEVEL == "DEBUG" else None,
    lifespan=lifespan,
)

# Step 5: Expose Prometheus HTTP Metrics
Instrumentator().instrument(app).expose(app)

# CORS middleware (allow all for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include webhook router
app.include_router(webhook.router)
app.include_router(agent_webhook.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        A dictionary containing the health status.
    """
    return {"status": "ok"}


@app.get("/ready")
async def ready_check() -> JSONResponse:
    """Ready check endpoint checking Redis, Qdrant and Database.

    Returns:
        JSONResponse with the status of each component and 200 or 503 status code.
    """
    redis_ok = False
    qdrant_ok = False
    db_ok = False

    # Check Redis
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        r.ping()
        redis_ok = True
    except Exception as e:
        logger.error("Ready check: Redis is down", error=str(e))

    # Check Qdrant
    try:
        # Send a lightweight HTTP check to Qdrant health endpoint
        response = httpx.get(f"{settings.QDRANT_URL}/healthz", timeout=1.0)
        if response.status_code == 200:
            qdrant_ok = True
        else:
            # Try general qdrant root as fallback
            response_root = httpx.get(f"{settings.QDRANT_URL}/", timeout=1.0)
            if response_root.status_code == 200:
                qdrant_ok = True
    except Exception as e:
        logger.error("Ready check: Qdrant is down", error=str(e))

    # Check Database
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error("Ready check: Database is down", error=str(e))

    status_code = status.HTTP_200_OK if (redis_ok and qdrant_ok and db_ok) else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "error",
            "redis": "ok" if redis_ok else "down",
            "qdrant": "ok" if qdrant_ok else "down",
            "database": "ok" if db_ok else "down"
        }
    )


# Exception Handlers to return structured JSON errors as required:
# {"error": {"code": 401, "message": "Invalid signature"}}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard FastAPI/Starlette HTTP Exceptions."""
    detail = exc.detail
    # Check if detail is already a dictionary structured correctly
    if isinstance(detail, dict) and "error" in detail:
        error_payload = detail
    else:
        error_payload = {
            "error": {
                "code": exc.status_code,
                "message": str(detail),
            }
        }
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle standard Request Validation Errors."""
    logger.warning("Validation error occurred", errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "message": "Validation Error",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unhandled exceptions."""
    logger.exception("An unhandled exception occurred", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Internal Server Error",
            }
        },
    )
