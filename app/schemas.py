from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """Standard API wrapper for success and error responses."""
    status: str
    message: str
    data: T | None = None

class MetricsDTO(BaseModel):
    topic_diversity: float
    c_npmi: float
    embedding_density: float
    intra_topic_similarity: float

class TopicDTO(BaseModel):
    topic_id: int
    label: str
    message_count: int
    keywords: List[str]

class SenderDTO(BaseModel):
    name: str
    message_count: int

class DateActivityDTO(BaseModel):
    date: str
    count: int

class HourActivityDTO(BaseModel):
    hour: int
    count: int

class ResultsSummaryDTO(BaseModel):
    metrics: MetricsDTO
    topic_count: int
    topics: List[TopicDTO]
    top_senders: List[SenderDTO]
    active_dates: List[DateActivityDTO]
    active_hours: List[HourActivityDTO]

class MessageDTO(BaseModel):
    message_id: str
    sender: str
    content: str
    timestamp: str

class TopicDetailDTO(BaseModel):
    topic_id: int
    label: str
    messages: List[MessageDTO]

class ContextMessageDTO(BaseModel):
    message_id: str
    sender: str
    content: str
    timestamp: str
    is_focused: bool

class MessageContextDTO(BaseModel):
    focused_message: MessageDTO
    context_messages: List[ContextMessageDTO]