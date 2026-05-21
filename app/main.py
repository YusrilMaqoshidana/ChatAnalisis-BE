"""
FastAPI Application Entry Point
================================
Inisialisasi dan konfigurasi utama FastAPI app.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.cache import get_redis_pool
from app.config import settings
from app.database import engine, init_db
from app.models import Base
from app.routes import jobs, topics


async def reset_database() -> None:
    """Drop semua tabel lalu create ulang (DEV ONLY)."""
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)


async def reset_redis() -> None:
    """Flush Redis termasuk queue ARQ (DEV ONLY)."""
    pool = await get_redis_pool()

    try:
        await pool.flushdb()
    finally:
        await pool.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan: startup & shutdown hooks."""

    reset_enabled = os.getenv("RESET_DEV", "false").lower() == "true"

    if reset_enabled:
        print("🧹 RESET_DEV=true → resetting database & redis...")

        await reset_database()
        await reset_redis()

        print("✅ Development environment reset complete")
    else:
        await init_db()

    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} is running!")

    yield

    print("👋 Application shutting down...")


def create_app() -> FastAPI:
    """Factory function untuk membuat FastAPI app."""
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # --- Rate Limiting ---
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes ---
    app.include_router(jobs.router)
    app.include_router(topics.router)

    # --- Health Check ---
    @app.get("/", tags=["Health Check"])
    def health_check() -> dict:
        """Root endpoint — cek apakah server berjalan."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


# Instance yang dijalankan oleh uvicorn
app = create_app()