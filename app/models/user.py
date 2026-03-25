"""
User Models (Pydantic Schemas)
==============================
Mendefinisikan schema untuk validasi request/response.

Best Practice:
- Pisahkan Base, Create, Update, dan Response schema
- Gunakan Field() untuk validasi dan dokumentasi
- Response schema hanya berisi data yang perlu dikirim ke client
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Enums
# ============================================================

class UserRole(str, Enum):
    """Role user dalam sistem."""
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


# ============================================================
# User Schemas
# ============================================================

class UserBase(BaseModel):
    """Base schema — field yang dipakai di banyak schema."""
    name: str = Field(..., min_length=2, max_length=100, examples=["Budi Santoso"])
    email: EmailStr = Field(..., examples=["budi@example.com"])
    role: UserRole = Field(default=UserRole.USER, examples=["user"])


class UserResponse(UserBase):
    """Schema untuk response single user."""
    id: int = Field(..., examples=[1])
    is_active: bool = Field(default=True)
    avatar_url: str | None = Field(default=None, examples=["https://i.pravatar.cc/150?img=1"])
    created_at: datetime = Field(..., examples=["2026-01-15T10:30:00"])

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Schema untuk response list user dengan metadata."""
    total: int = Field(..., description="Total jumlah user", examples=[10])
    users: list[UserResponse] = Field(..., description="Daftar user")


# ============================================================
# File Upload Schemas
# ============================================================

class FileUploadResponse(BaseModel):
    """Schema response setelah upload file berhasil."""
    filename: str = Field(..., description="Nama file original", examples=["document.pdf"])
    saved_as: str = Field(..., description="Nama file di server", examples=["20260316_abc123_document.pdf"])
    size_bytes: int = Field(..., description="Ukuran file dalam bytes", examples=[204800])
    size_human: str = Field(..., description="Ukuran file dalam format human-readable", examples=["200.0 KB"])
    content_type: str | None = Field(default=None, description="MIME type file", examples=["application/pdf"])
    upload_path: str = Field(..., description="Path file di server", examples=["uploads/20260316_abc123_document.pdf"])


class MultiFileUploadResponse(BaseModel):
    """Schema response untuk upload multiple files."""
    total_uploaded: int = Field(..., description="Jumlah file yang berhasil diupload")
    files: list[FileUploadResponse] = Field(..., description="Detail setiap file")


class FileInfoResponse(BaseModel):
    """Schema response untuk info file yang sudah ada."""
    filename: str
    size_bytes: int
    size_human: str
    modified_at: datetime


class ChatUploadResponse(BaseModel):
    """
    Schema response untuk upload file chat (in-memory, tanpa simpan ke disk).

    Fields:
        file_id: UUID v4 sebagai identifier session untuk proses selanjutnya.
        original_filename: Nama file asli dari client.
        size_bytes: Ukuran raw file yang diterima.
        size_human: Ukuran dalam format human-readable.
        content_type: MIME type file.
        extracted_size_bytes: Total ukuran isi setelah diekstrak (khusus .zip).
    """
    file_id: str = Field(..., description="UUID v4 — identifier session", examples=["a1b2c3d4-..."])
    original_filename: str = Field(..., description="Nama file asli", examples=["chat.txt"])
    size_bytes: int = Field(..., description="Ukuran raw file dalam bytes", examples=[204800])
    size_human: str = Field(..., description="Ukuran human-readable", examples=["200.0 KB"])
    content_type: str | None = Field(default=None, description="MIME type", examples=["text/plain"])
    extracted_size_bytes: int | None = Field(
        default=None,
        description="Total bytes setelah ekstraksi ZIP (None jika bukan .zip)",
        examples=[1048576],
    )
