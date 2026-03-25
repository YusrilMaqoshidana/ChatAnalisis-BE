"""
File Upload API Endpoints
=========================
Semua endpoint terkait File Upload ada di sini.

Best Practice:
- Gunakan UploadFile dari FastAPI (bukan Form) untuk file upload
- Validasi ada di service layer, route hanya menerima dan meneruskan
- Rate limiting via slowapi untuk mencegah abuse
- Dokumentasi endpoint lengkap untuk Swagger UI
"""

from fastapi import APIRouter, Depends, File, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_file_service
from app.core.config import settings
from app.models.user import (
    ChatUploadResponse,
    FileInfoResponse,
    FileUploadResponse,
    MultiFileUploadResponse,
)
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])

# Limiter instance — key berdasarkan IP address
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    summary="Upload single file",
    description="Upload satu file ke server. File akan divalidasi (ekstensi & ukuran) sebelum disimpan.",
    responses={
        400: {
            "description": "File tidak valid",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_extension": {
                            "summary": "Ekstensi tidak valid",
                            "value": {
                                "detail": "Ekstensi file tidak diperbolehkan. Ekstensi yang diperbolehkan: .txt, .zip"
                            },
                        },
                        "file_too_large": {
                            "summary": "File terlalu besar",
                            "value": {
                                "detail": "Ukuran file (15.0 MB) melebihi batas maksimal (10 MB)"
                            },
                        },
                    }
                }
            },
        }
    },
)
async def upload_file(
    file: UploadFile = File(..., description="File yang akan diupload"),
    service: FileService = Depends(get_file_service),
) -> FileUploadResponse:
    """
    **Upload File**

    Upload satu file ke server dengan validasi:
    - Ekstensi file harus sesuai daftar yang diperbolehkan
    - Ukuran file tidak boleh melebihi batas maksimal (default: 10 MB)
    - File akan disimpan dengan nama unik untuk menghindari overwrite
    """
    return await service.upload_file(file)


@router.post(
    "/upload-multiple",
    response_model=MultiFileUploadResponse,
    summary="Upload multiple files",
    description="Upload beberapa file sekaligus ke server.",
)
async def upload_multiple_files(
    files: list[UploadFile] = File(..., description="Files yang akan diupload"),
    service: FileService = Depends(get_file_service),
) -> MultiFileUploadResponse:
    """
    **Upload Multiple Files**

    Upload beberapa file sekaligus. Setiap file akan divalidasi secara individual.
    Jika satu file gagal validasi, proses akan berhenti dan error dikembalikan.
    """
    return await service.upload_multiple_files(files)


@router.get(
    "",
    response_model=list[FileInfoResponse],
    summary="List uploaded files",
    description="Mengambil daftar semua file yang sudah diupload ke server.",
)
def list_uploaded_files(
    service: FileService = Depends(get_file_service),
) -> list[FileInfoResponse]:
    """
    **Daftar File**

    Mengembalikan daftar semua file yang tersimpan di server
    beserta metadata (nama, ukuran, waktu modifikasi).
    """
    return service.get_uploaded_files()


@router.post(
    "/upload-chat",
    response_model=ChatUploadResponse,
    summary="Upload file chat (.txt / .zip)",
    description=(
        "Upload file hasil export chat WhatsApp. "
        "Hanya menerima **.txt** atau **.zip**. "
        f"Rate limit: **{settings.RATE_LIMIT_UPLOAD}** per IP. "
        "Diproses **sepenuhnya di memori** (tidak disimpan ke disk)."
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
