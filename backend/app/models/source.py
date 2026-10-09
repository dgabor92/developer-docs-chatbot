import ipaddress
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_url: str
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("base_url must use http or https scheme")
        if not parsed.netloc:
            raise ValueError("base_url must include a hostname")
        hostname = (parsed.hostname or "").lower()
        # Block localhost and unspecified host
        if hostname in ("localhost", "0.0.0.0", ""):
            raise ValueError("base_url must not point to localhost")
        # Block private/loopback/link-local IP addresses (SSRF guard)
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
                raise ValueError("base_url must not point to a private or reserved address")
        except ValueError as exc:
            if "private" in str(exc) or "reserved" in str(exc) or "loopback" in str(exc):
                raise
            # hostname is a domain name — DNS resolution happens at runtime
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
