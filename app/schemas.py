from typing import Any, Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Standard API wrapper for success and error responses."""

    status: str
    message: str
    data: T | None = None


class WSProgressMessage(BaseModel):
    """Progress message sent from WebSocket server to client."""

    status: str
    message: str | None = None
    data: Any | None = None


class JobProgressData(BaseModel):
    """Progress payload for background training jobs."""

    job_id: str
    status: str
    progress: int
    message: str
    created_at: str
    updated_at: str


class JobProgressResponse(BaseModel):
    """Response wrapper data model for job progress endpoint."""

    job_id: str
    status: str
    progress: int
    message: str