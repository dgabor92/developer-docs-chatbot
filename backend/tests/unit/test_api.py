"""Tests for FastAPI endpoints — DB and service calls are mocked."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api import health, sessions, sources


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with routers but no lifespan (no DB startup)."""
    app = FastAPI()
    app.include_router(health.router, prefix='/api')
    app.include_router(sources.router, prefix='/api')
    app.include_router(sessions.router, prefix='/api')
    return app


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _source_row(
    sid=None, name='Docs', url='https://x.com/', status='pending', chunks=0
) -> dict:
    return {
        'id': sid or uuid4(),
        'name': name,
        'base_url': url,
        'description': None,
        'status': status,
        'chunk_count': chunks,
        'error_msg': None,
        'created_at': _ts(),
        'updated_at': _ts(),
    }


def _session_row(sess_id=None, source_ids=None) -> dict:
    return {
        'id': sess_id or uuid4(),
        'title': None,
        'source_ids': source_ids or [],
        'created_at': _ts(),
        'updated_at': _ts(),
    }


# ── /api/health ───────────────────────────────────────────────────────────────

async def test_health_ok() -> None:
    app = _make_app()
    with (
        patch('app.api.health.get_pool') as mock_get_pool,
        patch('app.api.health.ollama_client') as mock_ollama,
        patch('app.api.health.anthropic_client') as mock_anthropic,
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_get_pool.return_value = mock_pool
        mock_ollama.is_available = AsyncMock(return_value=True)
        mock_anthropic.is_configured = MagicMock(return_value=True)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/health')

    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'ok'
    assert data['database'] == 'ok'
    assert data['ollama'] == 'ok'
    assert data['anthropic'] == 'configured'


async def test_health_degraded_when_ollama_down() -> None:
    app = _make_app()
    with (
        patch('app.api.health.get_pool') as mock_get_pool,
        patch('app.api.health.ollama_client') as mock_ollama,
        patch('app.api.health.anthropic_client') as mock_anthropic,
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_get_pool.return_value = mock_pool
        mock_ollama.is_available = AsyncMock(return_value=False)
        mock_anthropic.is_configured = MagicMock(return_value=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/health')

    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'degraded'
    assert data['ollama'] == 'error'


async def test_health_db_error() -> None:
    app = _make_app()
    with (
        patch('app.api.health.get_pool', side_effect=RuntimeError('no pool')),
        patch('app.api.health.ollama_client') as mock_ollama,
        patch('app.api.health.anthropic_client') as mock_anthropic,
    ):
        mock_ollama.is_available = AsyncMock(return_value=True)
        mock_anthropic.is_configured = MagicMock(return_value=True)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/health')

    assert resp.status_code == 200
    data = resp.json()
    assert data['database'] == 'error'
    assert data['status'] == 'degraded'


# ── /api/sources ──────────────────────────────────────────────────────────────

async def test_list_sources_empty() -> None:
    app = _make_app()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.list_sources = AsyncMock(return_value=[])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/sources')
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_sources_returns_rows() -> None:
    app = _make_app()
    rows = [_source_row(), _source_row()]
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.list_sources = AsyncMock(return_value=rows)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/sources')
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_source_not_found() -> None:
    app = _make_app()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.get_source = AsyncMock(return_value=None)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(f'/api/sources/{uuid4()}')
    assert resp.status_code == 404


async def test_get_source_found() -> None:
    app = _make_app()
    row = _source_row()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.get_source = AsyncMock(return_value=row)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(f'/api/sources/{row["id"]}')
    assert resp.status_code == 200
    assert resp.json()['name'] == row['name']


async def test_create_source_success() -> None:
    app = _make_app()
    row = _source_row(name='New Docs', url='https://docs.new.com/')
    with (
        patch('app.api.sources.sources_db') as mock_db,
        patch('app.api.sources.ingestion_service') as mock_ingest,
    ):
        mock_db.create_source = AsyncMock(return_value=row)
        mock_ingest.ingest_source = AsyncMock()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                '/api/sources',
                json={'name': 'New Docs', 'base_url': 'https://docs.new.com/'},
            )
    assert resp.status_code == 201
    assert resp.json()['name'] == 'New Docs'


async def test_create_source_conflict() -> None:
    import asyncpg
    app = _make_app()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.create_source = AsyncMock(
            side_effect=asyncpg.UniqueViolationError('unique violation')
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                '/api/sources',
                json={'name': 'Docs', 'base_url': 'https://example.com/'},
            )
    assert resp.status_code == 409


async def test_delete_source_not_found() -> None:
    app = _make_app()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.delete_source = AsyncMock(return_value=False)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.delete(f'/api/sources/{uuid4()}')
    assert resp.status_code == 404


async def test_delete_source_success() -> None:
    app = _make_app()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.delete_source = AsyncMock(return_value=True)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.delete(f'/api/sources/{uuid4()}')
    assert resp.status_code == 204


async def test_reindex_source_not_found() -> None:
    app = _make_app()
    with patch('app.api.sources.sources_db') as mock_db:
        mock_db.get_source = AsyncMock(return_value=None)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(f'/api/sources/{uuid4()}/reindex')
    assert resp.status_code == 404


async def test_reindex_source_already_indexing() -> None:
    app = _make_app()
    row = _source_row(status='indexing')
    with (
        patch('app.api.sources.sources_db') as mock_db,
        patch('app.api.sources.set_source_indexing_if_idle', AsyncMock(return_value=False)),
    ):
        mock_db.get_source = AsyncMock(return_value=row)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(f'/api/sources/{row["id"]}/reindex')
    assert resp.status_code == 409


async def test_reindex_source_success() -> None:
    app = _make_app()
    row = _source_row(status='ready')
    with (
        patch('app.api.sources.sources_db') as mock_db,
        patch('app.api.sources.set_source_indexing_if_idle', AsyncMock(return_value=True)),
        patch('app.api.sources.ingestion_service') as mock_ingest,
    ):
        mock_db.get_source = AsyncMock(return_value=row)
        mock_ingest.ingest_source = AsyncMock()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(f'/api/sources/{row["id"]}/reindex')
    assert resp.status_code == 200


# ── /api/sessions ─────────────────────────────────────────────────────────────

async def test_list_sessions_empty() -> None:
    app = _make_app()
    with patch('app.api.sessions.list_sessions', AsyncMock(return_value=[])):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/sessions')
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_session_success() -> None:
    app = _make_app()
    row = _session_row()
    with patch('app.api.sessions.create_session', AsyncMock(return_value=row)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post('/api/sessions', json={'source_ids': []})
    assert resp.status_code == 201


async def test_get_session_not_found() -> None:
    app = _make_app()
    with patch('app.api.sessions.get_session', AsyncMock(return_value=None)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(f'/api/sessions/{uuid4()}')
    assert resp.status_code == 404


async def test_get_session_with_messages_sources_as_string() -> None:
    """JSONB sources arrive as a JSON string from asyncpg — lines 39-40 in sessions.py."""
    app = _make_app()
    sess_id = uuid4()
    row = _session_row(sess_id=sess_id)
    sources_json = json.dumps([{'url': 'https://x.com', 'title': 'X', 'score': 0.9}])
    msg_row = {
        'id': uuid4(),
        'session_id': sess_id,
        'role': 'assistant',
        'content': 'Answer',
        'sources': sources_json,  # raw string, simulating asyncpg JSONB
        'created_at': _ts(),
    }
    with (
        patch('app.api.sessions.get_session', AsyncMock(return_value=row)),
        patch('app.api.sessions.list_messages', AsyncMock(return_value=[msg_row])),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(f'/api/sessions/{sess_id}')
    assert resp.status_code == 200
    data = resp.json()
    assert data['messages'][0]['sources'][0]['url'] == 'https://x.com'


async def test_get_session_with_messages() -> None:
    app = _make_app()
    sess_id = uuid4()
    row = _session_row(sess_id=sess_id)
    msg_row = {
        'id': uuid4(),
        'session_id': sess_id,
        'role': 'user',
        'content': 'Hello',
        'sources': None,
        'created_at': _ts(),
    }
    with (
        patch('app.api.sessions.get_session', AsyncMock(return_value=row)),
        patch('app.api.sessions.list_messages', AsyncMock(return_value=[msg_row])),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(f'/api/sessions/{sess_id}')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data['messages']) == 1


async def test_delete_session_not_found() -> None:
    app = _make_app()
    with patch('app.api.sessions.delete_session', AsyncMock(return_value=False)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.delete(f'/api/sessions/{uuid4()}')
    assert resp.status_code == 404


async def test_delete_session_success() -> None:
    app = _make_app()
    with patch('app.api.sessions.delete_session', AsyncMock(return_value=True)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.delete(f'/api/sessions/{uuid4()}')
    assert resp.status_code == 204


async def test_send_message_session_not_found() -> None:
    app = _make_app()
    with patch('app.api.sessions.get_session', AsyncMock(return_value=None)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                f'/api/sessions/{uuid4()}/messages', json={'content': 'Hello'}
            )
    assert resp.status_code == 404


async def test_send_message_streams_sse() -> None:
    app = _make_app()
    sess_id = uuid4()
    row = _session_row(sess_id=sess_id)

    async def fake_stream(sid, content):
        yield 'token', {'content': 'Hello '}
        yield 'token', {'content': 'world'}
        yield 'done', {'message_id': str(uuid4()), 'session_id': str(sess_id)}

    with (
        patch('app.api.sessions.get_session', AsyncMock(return_value=row)),
        patch('app.api.sessions.chat_service') as mock_chat,
    ):
        mock_chat.stream_message = fake_stream
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                f'/api/sessions/{sess_id}/messages', json={'content': 'Hi'}
            )
    assert resp.status_code == 200
    assert 'text/event-stream' in resp.headers['content-type']
    body = resp.text
    assert 'event: token' in body
    assert 'event: done' in body


async def test_send_message_stream_error_emits_error_event() -> None:
    app = _make_app()
    sess_id = uuid4()
    row = _session_row(sess_id=sess_id)

    async def failing_stream(sid, content):
        raise RuntimeError('unexpected crash')
        yield  # make it a generator

    with (
        patch('app.api.sessions.get_session', AsyncMock(return_value=row)),
        patch('app.api.sessions.chat_service') as mock_chat,
    ):
        mock_chat.stream_message = failing_stream
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                f'/api/sessions/{sess_id}/messages', json={'content': 'Hi'}
            )
    assert resp.status_code == 200
    assert 'event: error' in resp.text
