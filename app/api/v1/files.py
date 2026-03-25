"""
File Upload API Endpoints
=========================
Hanya satu endpoint: upload file chat WhatsApp (.txt / .zip).
Semua validasi ada di service layer. Rate limiting via slowapi.
"""

from fastapi import APIRouter, Depends, File, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_file_service
from app.core.config import settings
from app.models.file_model import ChatUploadResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])

# Rate limiter berdasarkan IP address
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/upload-chat",
    response_model=ChatUploadResponse,
    summary="Upload file chat WhatsApp (.txt / .zip)",
    description=(
        "Upload file hasil export chat WhatsApp. "
        "Hanya menerima **.txt** atau **.zip**. "
        f"Rate limit: **{settings.RATE_LIMIT_UPLOAD}** per IP. "
        "Diproses **sepenuhnya di memori** — tidak disimpan ke disk."
    ),
    responses={
        400: {
            "description": "File tidak valid",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_extension": {
                            "summary": "Ekstensi tidak valid",
                            "value": {"detail": "Format file '.pdf' tidak didukung. Hanya file .txt atau .zip yang diperbolehkan."},
                        },
                        "zip_bomb": {
                            "summary": "Zip bomb terdeteksi",
                            "value": {"detail": "Ukuran konten ZIP setelah diekstrak (500.0 MB) melebihi batas maksimal (200 MB). File mungkin adalah zip bomb."},
                        },
                        "file_too_large": {
                            "summary": "File terlalu besar",
                            "value": {"detail": "Ukuran file (15.0 MB) melebihi batas maksimal (10 MB)"},
                        },
                    }
                }
            },
        },
        408: {
            "description": "Timeout",
            "content": {
                "application/json": {
                    "example": {"detail": "Proses upload melebihi batas waktu (30 detik)."}
                }
            },
        },
        429: {
            "description": "Rate limit terlampaui",
            "content": {
                "application/json": {
                    "example": {"detail": "Rate limit exceeded: 5 per 1 minute"}
                }
            },
        },
    },
)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_chat_file(
    request: Request,
    file: UploadFile = File(..., description="File chat (.txt atau .zip)"),
    service: FileService = Depends(get_file_service),
) -> ChatUploadResponse:
    """
    **Upload File Chat** (In-Memory · Rate Limited · Zip Bomb Protected)

    Keamanan:
    - ✅ Hanya **.txt** atau **.zip**
    - ✅ Rate limit **5 upload/menit per IP** (HTTP 429 jika terlampaui)
    - ✅ ZIP bomb check — max extracted **200 MB** (~3 tahun chat aktif)
    - ✅ Timeout **30 detik** (HTTP 408 jika terlampaui)
    - ✅ Diproses di memori, **tidak disimpan ke disk**
    - ✅ Response berisi **UUID** sebagai identifier session
    """
    return await service.process_chat_file(file)
