"""
FastAPI Application Entry Point
================================
Inisialisasi dan konfigurasi utama FastAPI app.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import analysis
from app.schemas import BaseResponse


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Factory function untuk membuat FastAPI app."""
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes ---
    app.include_router(analysis.router)

    # --- Health Check ---
    @app.get("/", tags=["Health Check"], response_model=BaseResponse[dict], response_model_exclude_none=True)
    def health_check() -> BaseResponse[dict]:
        """Root endpoint — cek apakah server berjalan."""
        return BaseResponse(
            status="success",
            message="Server berjalan normal",
            data={
                "status": "healthy",
                "app": settings.APP_NAME,
                "version": settings.APP_VERSION,
            },
        )

    return app


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=BaseResponse(status="error", message=str(exc.detail)).model_dump(exclude_none=True),
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    message = exc.errors()[0]["msg"] if exc.errors() else "Request tidak valid"
    return JSONResponse(
        status_code=422,
        content=BaseResponse(status="error", message=message).model_dump(exclude_none=True),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=BaseResponse(status="error", message="Terjadi kesalahan pada server").model_dump(exclude_none=True),
    )


# Instance yang dijalankan oleh uvicorn
app = create_app()