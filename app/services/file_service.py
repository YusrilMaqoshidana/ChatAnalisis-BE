"""
File Service (Business Logic Layer)
====================================
Memproses file chat WhatsApp (.txt/.zip) sepenuhnya di memori.

Fitur keamanan:
- Validasi ekstensi: hanya .txt / .zip
- Timeout via asyncio.wait_for
- ZIP bomb protection
- File .vcf dalam ZIP diabaikan (dianggap dihapus saat ekstraksi)
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
from app.utils.file_utils import (
    apply_full_preprocessing,
    filter_messages_by_timeframe,
    format_file_size,
    parse_whatsapp_txt_bytes,
)

# Ekstensi yang diperbolehkan untuk upload file chat
CHAT_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".zip"})


class FileService:

    _REMOVED_ZIP_SUFFIXES: tuple[str, ...] = (".vcf",)

    async def process_chat_file(self, file: UploadFile, timeframe: str = "all") -> ChatUploadResponse:
        try:
            result = await asyncio.wait_for(
                self._do_process_chat_file(file, timeframe=timeframe),
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

    async def _do_process_chat_file(self, file: UploadFile, timeframe: str = "all") -> ChatUploadResponse:
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
        parsed_messages: list[dict[str, str]] = []
        if ext == ".zip":
            extracted_size = self._check_zip_bomb(content)
            parsed_messages = self._parse_zip_txt_messages(content)
        else:
            parsed_messages = parse_whatsapp_txt_bytes(content)

        selected_messages, timeframe_filtered_count = filter_messages_by_timeframe(parsed_messages, timeframe=timeframe)
        preprocessed_messages, preprocessing_stats = apply_full_preprocessing(selected_messages)

        # 6. UUID sebagai identifier session (tidak simpan ke disk)
        file_id = str(uuid.uuid4())

        return ChatUploadResponse(
            file_id=file_id,
            parsed_messages=preprocessed_messages,
        )

    def _parse_zip_txt_messages(self, content: bytes) -> list[dict[str, str]]:
        """Ekstrak semua file .txt dari ZIP, lalu parse menjadi baris chat."""
        parsed_rows: list[dict[str, str]] = []

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue

                    name_lower = info.filename.lower()
                    if name_lower.endswith(self._REMOVED_ZIP_SUFFIXES):
                        continue
                    if not name_lower.endswith(".txt"):
                        continue

                    file_bytes = zf.read(info)
                    parsed_rows.extend(parse_whatsapp_txt_bytes(file_bytes))
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File ZIP tidak valid atau rusak.",
            )

        return parsed_rows

    def _check_zip_bomb(self, content: bytes) -> int:
        max_bytes = settings.ZIP_MAX_EXTRACTED_MB * 1024 * 1024

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # Abaikan file contact card (*.vcf) dari hasil ekstraksi ZIP.
                total_extracted = sum(
                    info.file_size
                    for info in zf.infolist()
                    if not info.is_dir() and not info.filename.lower().endswith(self._REMOVED_ZIP_SUFFIXES)
                )
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

file_service = FileService()
