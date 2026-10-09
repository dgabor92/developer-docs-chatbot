"""Tests for Pydantic models."""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.session import (
    MessageCreate,
    MessageResponse,
    SessionCreate,
    SessionResponse,
    SessionWithMessages,
    SourceCitation,
)
from app.models.source import SourceCreate, SourceResponse


# ── SourceCreate ──────────────────────────────────────────────────────────────

class TestSourceCreate:
    def test_valid(self) -> None:
        s = SourceCreate(name='FastAPI Docs', base_url='https://fastapi.tiangolo.com/')
        assert s.name == 'FastAPI Docs'
        assert s.base_url == 'https://fastapi.tiangolo.com/'
        assert s.description is None

    def test_with_description(self) -> None:
        s = SourceCreate(name='Docs', base_url='https://example.com/', description='desc')
        assert s.description == 'desc'

    def test_rejects_non_http_scheme(self) -> None:
        with pytest.raises(ValidationError, match='http or https'):
            SourceCreate(name='X', base_url='ftp://example.com/')

    def test_rejects_localhost(self) -> None:
        with pytest.raises(ValidationError, match='localhost'):
            SourceCreate(name='X', base_url='http://localhost/')

    def test_rejects_0_0_0_0(self) -> None:
        with pytest.raises(ValidationError, match='localhost'):
            SourceCreate(name='X', base_url='http://0.0.0.0/')

    def test_rejects_private_ip(self) -> None:
        with pytest.raises(ValidationError, match='private'):
            SourceCreate(name='X', base_url='http://192.168.1.1/')

    def test_rejects_loopback_ip(self) -> None:
        with pytest.raises(ValidationError, match='private'):
            SourceCreate(name='X', base_url='http://127.0.0.1/')

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            SourceCreate(name='', base_url='https://example.com/')

    def test_rejects_no_hostname(self) -> None:
        with pytest.raises(ValidationError, match='hostname'):
            SourceCreate(name='X', base_url='http://')

    def test_http_scheme_accepted(self) -> None:
        s = SourceCreate(name='X', base_url='http://example.com/')
        assert s.base_url == 'http://example.com/'


# ── SessionCreate ─────────────────────────────────────────────────────────────

class TestSessionCreate:
    def test_empty_source_ids(self) -> None:
        s = SessionCreate()
        assert s.source_ids == []

    def test_with_source_ids(self) -> None:
        uid = uuid.uuid4()
        s = SessionCreate(source_ids=[uid])
        assert s.source_ids == [uid]

    def test_too_many_source_ids(self) -> None:
        with pytest.raises(ValidationError):
            SessionCreate(source_ids=[uuid.uuid4() for _ in range(51)])


# ── MessageCreate ─────────────────────────────────────────────────────────────

class TestMessageCreate:
    def test_valid(self) -> None:
        m = MessageCreate(content='Hello')
        assert m.content == 'Hello'

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageCreate(content='')

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageCreate(content='x' * 8001)


# ── SourceCitation ────────────────────────────────────────────────────────────

class TestSourceCitation:
    def test_valid(self) -> None:
        c = SourceCitation(url='https://example.com', title='Title', score=0.9)
        assert c.score == 0.9

    def test_no_title(self) -> None:
        c = SourceCitation(url='https://example.com', title=None, score=0.5)
        assert c.title is None


# ── SessionResponse / SessionWithMessages ────────────────────────────────────

class TestSessionResponse:
    def _make(self) -> SessionResponse:
        now = datetime.now(timezone.utc)
        return SessionResponse(
            id=uuid.uuid4(),
            title=None,
            source_ids=[],
            created_at=now,
            updated_at=now,
        )

    def test_valid(self) -> None:
        s = self._make()
        assert s.title is None

    def test_with_messages(self) -> None:
        now = datetime.now(timezone.utc)
        sess_id = uuid.uuid4()
        msg = MessageResponse(
            id=uuid.uuid4(),
            session_id=sess_id,
            role='user',
            content='Hi',
            sources=None,
            created_at=now,
        )
        sw = SessionWithMessages(
            id=sess_id,
            title=None,
            source_ids=[],
            created_at=now,
            updated_at=now,
            messages=[msg],
        )
        assert len(sw.messages) == 1
