"""
UdyamAI — FastAPI Application Entry Point
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.config import get_settings

settings = get_settings()

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.backend_log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("udyamai")


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    logger.info("🚀 UdyamAI starting up ...")
    logger.info("Environment: %s", settings.app_env)
    logger.info("Database: %s", settings.database_url[:40] + "...")
    logger.info("Gemini model: %s", settings.gemini_model)
    logger.info("Qdrant: %s:%s", settings.qdrant_host, settings.qdrant_port)
    logger.info("Redis: %s", settings.redis_url)

    # Ensure Qdrant collection exists
    try:
        from app.ai.rag_retriever import RAGRetriever
        rag = RAGRetriever()
        await rag.ensure_collection()
        logger.info("✅ Qdrant collection ready")
    except Exception as e:
        logger.warning("⚠️  Qdrant not available at startup: %s", e)

    yield

    logger.info("🛑 UdyamAI shutting down ...")


# ─── Application ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="UdyamAI API",
        description=(
            "AI-Driven Hyper-Local Business Advisory and Financial Structuring Assistant "
            "for Rural Micro-Entrepreneurs in India."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request Timing Middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.3f}s"
        return response

    # ── Global Exception Handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s %s — %s", request.method, request.url, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again."},
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": "UdyamAI API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()


# ─── Dev Runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.backend_reload,
        log_level=settings.backend_log_level,
    )
