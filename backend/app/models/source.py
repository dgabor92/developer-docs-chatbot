from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, field_validator


class SourceCreate(BaseModel):
    name: str
    base_url: str
    description: str | None = None

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('base_url must use http or https scheme')
        if not parsed.netloc:
            raise ValueError('base_url must include a hostname')
        return v


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
