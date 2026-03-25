"""
File Service (Business Logic Layer)
====================================
Business logic untuk operasi file upload.

Best Practice:
- Validasi file (size, extension) di service layer
- Service mengorkestrasi utils dan I/O operations
- Return structured response, bukan raw data
"""

from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.models.user import FileInfoResponse, FileUploadResponse, MultiFileUploadResponse
from app.utils.file_utils import (
    format_file_size,
    generate_unique_filename,
    get_allowed_extensions_str,
    validate_file_extension,
)


# Ekstensi yang diperbolehkan untuk upload file chat
CHAT_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".zip"})


class FileService:
    """Service untuk operasi upload dan manajemen file."""

    async def upload_file(self, file: UploadFile) -> FileUploadResponse:
        """
        Upload single file ke server.

        Steps:
        1. Validasi ekstensi file
        2. Baca content file
        3. Validasi ukuran file
        4. Generate nama unik
        5. Simpan ke disk
        6. Return metadata

        Args:
            file: UploadFile dari FastAPI

        Returns:
            FileUploadResponse dengan detail file yang diupload

        Raises:
            HTTPException 400: Jika file tidak valid (ekstensi/ukuran)
        """
        # 1. Validasi ekstensi
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nama file tidak boleh kosong",
            )

        if not validate_file_extension(file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ekstensi file tidak diperbolehkan. "
                    f"Ekstensi yang diperbolehkan: {get_allowed_extensions_str()}"
                ),
            )

        # 2. Baca content
        content = await file.read()

        # 3. Validasi ukuran
        file_size = len(content)
        if file_size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ukuran file ({format_file_size(file_size)}) melebihi batas "
                    f"maksimal ({settings.MAX_FILE_SIZE_MB} MB)"
                ),
            )

        # 4. Generate nama unik
        unique_name = generate_unique_filename(file.filename)

        # 5. Simpan ke disk (async)
        upload_path = settings.upload_path / unique_name
        async with aiofiles.open(upload_path, "wb") as f:
            await f.write(content)

        # 6. Return response
        return FileUploadResponse(
            filename=file.filename,
            saved_as=unique_name,
            size_bytes=file_size,
            size_human=format_file_size(file_size),
            content_type=file.content_type,
            upload_path=str(upload_path),
        )

    async def process_chat_file(self, file: UploadFile) -> "ChatUploadResponse":
        """
        Proses file chat sepenuhnya di memori (tanpa simpan ke disk).

        Fitur keamanan:
        - Validasi ekstensi: hanya .txt / .zip
        - Timeout: seluruh proses dibatasi UPLOAD_TIMEOUT_SECONDS
        - Zip bomb protection: total extracted size dibatasi ZIP_MAX_EXTRACTED_MB
        - UUID file ID: tidak ada data yang ditulis ke disk
        """
        import asyncio
        import io
        import uuid
        import zipfile
        from pathlib import Path as _Path

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

    async def _do_process_chat_file(self, file: UploadFile) -> "ChatUploadResponse":
        """Internal: logika proses file chat (dipanggil dalam wait_for)."""
        import io
        import uuid
        import zipfile
        from pathlib import Path as _Path
        from app.models.user import ChatUploadResponse

        # 1. Validasi nama file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nama file tidak boleh kosong",
            )

        # 2. Validasi ekstensi
        ext = _Path(file.filename).suffix.lower()
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
        Periksa potensi zip bomb dengan menghitung total ukuran files di dalam ZIP.

        Returns:
            Total extracted size dalam bytes.

        Raises:
            HTTPException 400: Jika total extracted size melebihi ZIP_MAX_EXTRACTED_MB.
        """
        import io
        import zipfile

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



    async def upload_multiple_files(self, files: list[UploadFile]) -> MultiFileUploadResponse:
        """
        Upload multiple files sekaligus.

        Args:
            files: List UploadFile dari FastAPI

        Returns:
            MultiFileUploadResponse dengan detail semua file
        """
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimal satu file harus diupload",
            )

        results: list[FileUploadResponse] = []
        for file in files:
            result = await self.upload_file(file)
            results.append(result)

        return MultiFileUploadResponse(
            total_uploaded=len(results),
            files=results,
        )

    def get_uploaded_files(self) -> list[FileInfoResponse]:
        """
        List semua file yang sudah diupload.

        Returns:
            List FileInfoResponse dengan metadata setiap file
        """
        upload_dir = settings.upload_path
        if not upload_dir.exists():
            return []

        files: list[FileInfoResponse] = []
        for file_path in sorted(upload_dir.iterdir()):
            if file_path.is_file() and not file_path.name.startswith("."):
                stat = file_path.stat()
                files.append(
                    FileInfoResponse(
                        filename=file_path.name,
                        size_bytes=stat.st_size,
                        size_human=format_file_size(stat.st_size),
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                    )
                )

        return files


# Singleton instance
file_service = FileService()
