from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """Standard API wrapper for success and error responses."""

    status: str
    message: str
    data: T | None = None