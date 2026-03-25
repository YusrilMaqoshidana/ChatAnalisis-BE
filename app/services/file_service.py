"""
File Service (Business Logic Layer)
====================================
Memproses file chat WhatsApp (.txt/.zip) sepenuhnya di memori.

Fitur keamanan:
- Validasi ekstensi: hanya .txt / .zip
- Timeout via asyncio.wait_for
- ZIP bomb protection
- UUID sebagai identifier (tanpa disk write)
"""

import asyncio
import io
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.models.file_model import ChatUploadResponse
from app.utils.file_utils import format_file_size

# Ekstensi yang diperbolehkan untuk upload file chat
CHAT_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".zip"})


class FileService:
    """Service untuk memproses file chat WhatsApp di memori."""

    async def process_chat_file(self, file: UploadFile) -> ChatUploadResponse:
        """
        Proses file chat sepenuhnya di memori (tanpa simpan ke disk).

        Keamanan:
        - Validasi ekstensi: hanya .txt / .zip
        - Timeout: UPLOAD_TIMEOUT_SECONDS
        - ZIP bomb protection: ZIP_MAX_EXTRACTED_MB
        - UUID sebagai file identifier
        """
        try:
            result = await asyncio.wait_for(
                self._do_process_chat_file(file),
                timeout=settings.UPLOAD_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=(
                    f"Proses upload melebihi batas waktu "
                    f"({settings.UPLOAD_TIMEOUT_SECONDS} detik). "
                    "Coba lagi dengan file yang lebih kecil."
                ),
            )
        return result

    async def _do_process_chat_file(self, file: UploadFile) -> ChatUploadResponse:
        """Internal: logika proses file chat."""
        # 1. Validasi nama file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nama file tidak boleh kosong",
            )

        # 2. Validasi ekstensi
        ext = Path(file.filename).suffix.lower()
        if ext not in CHAT_ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Format file '{ext or '(tanpa ekstensi)'}' tidak didukung. "
                    "Hanya file .txt atau .zip yang diperbolehkan."
                ),
            )

        # 3. Baca ke memori
        content = await file.read()
        file_size = len(content)

        # 4. Validasi ukuran raw file
        if file_size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ukuran file ({format_file_size(file_size)}) melebihi batas "
                    f"maksimal ({settings.MAX_FILE_SIZE_MB} MB)"
                ),
            )

        # 5. ZIP bomb protection
        extracted_size: int | None = None
        if ext == ".zip":
            extracted_size = self._check_zip_bomb(content)

        # 6. UUID sebagai identifier session (tidak simpan ke disk)
        file_id = str(uuid.uuid4())

        return ChatUploadResponse(
            file_id=file_id,
            original_filename=file.filename,
            size_bytes=file_size,
            size_human=format_file_size(file_size),
            content_type=file.content_type,
            extracted_size_bytes=extracted_size,
        )

    def _check_zip_bomb(self, content: bytes) -> int:
        """
        Hitung total ukuran file di dalam ZIP sebelum diekstrak.

        Returns:
            Total extracted size dalam bytes.

        Raises:
            HTTPException 400: Jika melebihi ZIP_MAX_EXTRACTED_MB atau ZIP rusak.
        """
        max_bytes = settings.ZIP_MAX_EXTRACTED_MB * 1024 * 1024

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                total_extracted = sum(info.file_size for info in zf.infolist())
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File ZIP tidak valid atau rusak.",
            )

        if total_extracted > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ukuran konten ZIP setelah diekstrak "
                    f"({format_file_size(total_extracted)}) melebihi batas maksimal "
                    f"({settings.ZIP_MAX_EXTRACTED_MB} MB). "
                    "File mungkin adalah zip bomb."
                ),
            )

        return total_extracted


# Singleton instance
file_service = FileService()
