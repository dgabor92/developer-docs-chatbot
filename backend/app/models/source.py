from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class SourceCreate(BaseModel):
    name: str
    base_url: str
    description: str | None = None


class SourceResponse(BaseModel):
    id: UUID
    name: str
    base_url: str
    description: str | None
    status: str
    chunk_count: int
    error_msg: str | None
    created_at: datetime
    updated_at: datetime
