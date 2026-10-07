from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionCreate(BaseModel):
    source_ids: list[UUID] = []


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
    content: str


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    sources: list[SourceCitation] | None
    created_at: datetime


class SessionWithMessages(SessionResponse):
    messages: list[MessageResponse]
