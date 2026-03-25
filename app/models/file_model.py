"""
Models (Pydantic Schemas)
=========================
Hanya schema yang dibutuhkan untuk endpoint upload chat.
"""

from pydantic import BaseModel, Field


class ChatUploadResponse(BaseModel):
    """
    Response untuk upload file chat (in-memory, tanpa simpan ke disk).

    Fields:
        file_id: UUID v4 sebagai identifier session.
        original_filename: Nama file asli dari client.
        size_bytes: Ukuran raw file yang diterima.
        size_human: Ukuran dalam format human-readable.
        content_type: MIME type file.
        extracted_size_bytes: Total ukuran isi setelah diekstrak (khusus .zip).
    """
    file_id: str = Field(..., description="UUID v4 — identifier session", examples=["a1b2c3d4-e5f6-..."])
    original_filename: str = Field(..., description="Nama file asli", examples=["chat.txt"])
    size_bytes: int = Field(..., description="Ukuran raw file dalam bytes", examples=[204800])
    size_human: str = Field(..., description="Ukuran human-readable", examples=["200.0 KB"])
    content_type: str | None = Field(default=None, description="MIME type", examples=["text/plain"])
    extracted_size_bytes: int | None = Field(
        default=None,
        description="Total bytes setelah ekstraksi ZIP (None jika bukan .zip)",
        examples=[1048576],
    )
