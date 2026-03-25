"""
FastAPI Application Entry Point
================================
Inisialisasi dan konfigurasi utama FastAPI app.

Best Practice:
- App factory pattern (bisa dipakai untuk testing)
- CORS middleware dikonfigurasi dari settings
- Lifespan event untuk setup/teardown
- Health check endpoint di root
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.models.user import UserListResponse, UserResponse
from app.services.user_service import user_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan event handler.
    - Startup: buat folder uploads jika belum ada
    - Shutdown: cleanup jika diperlukan
    """
    # === STARTUP ===
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Upload directory ready: {settings.upload_path.absolute()}")
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} is running!")

    yield

    # === SHUTDOWN ===
    print("👋 Application shutting down...")


def create_app() -> FastAPI:
    """
    Factory function untuk membuat FastAPI app.
    Berguna untuk testing — bisa buat app dengan konfigurasi berbeda.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",          # Swagger UI
        redoc_url="/redoc",        # ReDoc
        openapi_url="/openapi.json",
    )

    # --- Rate Limiting ---
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes ---
    app.include_router(v1_router)

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
