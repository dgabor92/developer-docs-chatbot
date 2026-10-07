from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    source_ids: list[UUID] = Field(default_factory=list, max_length=50)


class SessionResponse(BaseModel):
    id: UUID
    title: str | None
    source_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class SourceCitation(BaseModel):
    url: str
    title: str | None
    score: float


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    sources: list[SourceCitation] | None
    created_at: datetime


class SessionWithMessages(SessionResponse):
    messages: list[MessageResponse]
