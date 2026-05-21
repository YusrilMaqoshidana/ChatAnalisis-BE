from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class ParsedChatMessage(BaseModel):
    timestamp: datetime = Field(..., description="Waktu pesan", examples=["2026-04-06T09:41:00"])
    pengirim: str = Field(..., description="Nama pengirim", examples=["Budi"])
    pesan: str = Field(..., description="Isi pesan", examples=["Halo semua"])
    pesan_preprocessed: str = Field(
        ...,
        description="Pesan setelah preprocessing (normalisasi + cleaning)",
    )


class ChatUploadResponse(BaseModel):
    file_id: str = Field(..., description="UUID v4 — identifier session", examples=["a1b2c3d4-e5f6-..."])
    parsed_messages: list[ParsedChatMessage] = Field(
        default_factory=list,
    )
 
 
class JobResponse(BaseModel):
    """Response untuk POST /topics/train dan POST /topics/infer."""
    job_id: str
    type: str       # 'train' | 'infer'
    status: str     # 'queued' | 'running' | 'done' | 'error'
 
    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: str
    error_msg: str | None = None
    model_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class MessageOut(BaseModel):
    id: str
    sender: str
    content: str
    sent_at: datetime
    probability: float | None = None


class TopicSummary(BaseModel):
    id: str
    model_id: str
    topic_number: int
    keywords: list[str]
    label: str | None = None
    message_count: int

    model_config = ConfigDict(protected_namespaces=())


class TopicDetail(TopicSummary):
    messages: list[MessageOut] = Field(default_factory=list)

    model_config = ConfigDict(protected_namespaces=())