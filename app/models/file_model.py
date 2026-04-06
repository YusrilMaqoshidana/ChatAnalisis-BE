"""
Models (Pydantic Schemas)
=========================
Hanya schema yang dibutuhkan untuk endpoint upload chat.
"""

from pydantic import BaseModel, Field


class ParsedChatMessage(BaseModel):
    tanggal: str = Field(..., description="Tanggal chat", examples=["06/04/26"])
    waktu: str = Field(..., description="Waktu chat", examples=["9.41 AM"])
    pengirim: str = Field(..., description="Nama pengirim", examples=["Budi"])
    pesan: str = Field(..., description="Isi pesan", examples=["Halo semua"])
    pesan_preprocessed: str = Field(
        ...,
        description="Pesan setelah preprocessing (normalisasi + cleaning)",
        examples=["halo semua"],
    )


class ChatUploadResponse(BaseModel):
    file_id: str = Field(..., description="UUID v4 — identifier session", examples=["a1b2c3d4-e5f6-..."])
    parsed_messages: list[ParsedChatMessage] = Field(
        default_factory=list,
        description="Hasil akhir parsing + preprocessing",
    )
