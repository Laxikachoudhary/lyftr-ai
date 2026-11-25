
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    session_id: str
    response: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    latency_ms: float = 0
    key_id: str = ""
    fallback_attempts: int = 0
    response_source: str = ""


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: Optional[str] = None
    latency_ms: float = 0
    key_id: Optional[str] = None
    fallback_attempts: int = 0
    response_source: Optional[str] = None
    created_at: Optional[str] = None


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[MessageResponse]


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: Optional[str] = None
    last_message: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
