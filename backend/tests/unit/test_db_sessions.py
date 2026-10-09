"""Tests for app/db/sessions.py — all DB calls are mocked."""
import math
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.sessions import (
    create_message,
    create_session,
    delete_message,
    delete_session,
    get_session,
    list_messages,
    list_sessions,
    search_chunks,
    update_session_title,
)
from app.exceptions import EmbeddingError


def _make_pool(fetchrow=None, fetch=None, execute_return='UPDATE 0'):
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow)
    pool.fetch = AsyncMock(return_value=fetch or [])
    pool.execute = AsyncMock(return_value=execute_return)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow)

    # conn.transaction() must return an async context manager (not a coroutine)
    mock_txn = MagicMock()
    mock_txn.__aenter__ = AsyncMock(return_value=None)
    mock_txn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_txn)

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    pool.acquire = _acquire
    pool._mock_conn = mock_conn
    return pool


# ── create_session ────────────────────────────────────────────────────────────

async def test_create_session_returns_dict() -> None:
    sid = uuid4()
    row = {'id': sid, 'source_ids': [], 'title': None}
    pool = _make_pool(fetchrow=row)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await create_session([])
    assert result['id'] == sid


# ── get_session ───────────────────────────────────────────────────────────────

async def test_get_session_found() -> None:
    sid = uuid4()
    row = {'id': sid}
    pool = _make_pool(fetchrow=row)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await get_session(sid)
    assert result == {'id': sid}


async def test_get_session_not_found() -> None:
    pool = _make_pool(fetchrow=None)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await get_session(uuid4())
    assert result is None


# ── list_sessions ─────────────────────────────────────────────────────────────

async def test_list_sessions_empty() -> None:
    pool = _make_pool(fetch=[])
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await list_sessions()
    assert result == []


async def test_list_sessions_returns_dicts() -> None:
    rows = [{'id': uuid4()}, {'id': uuid4()}]
    pool = _make_pool(fetch=rows)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await list_sessions()
    assert len(result) == 2


# ── delete_session ────────────────────────────────────────────────────────────

async def test_delete_session_found() -> None:
    pool = _make_pool(execute_return='DELETE 1')
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await delete_session(uuid4())
    assert result is True


async def test_delete_session_not_found() -> None:
    pool = _make_pool(execute_return='DELETE 0')
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await delete_session(uuid4())
    assert result is False


# ── update_session_title ──────────────────────────────────────────────────────

async def test_update_session_title() -> None:
    pool = _make_pool()
    with patch('app.db.sessions.get_pool', return_value=pool):
        await update_session_title(uuid4(), 'New Title')
    pool.execute.assert_called_once()


# ── create_message ────────────────────────────────────────────────────────────

async def test_create_message_no_sources() -> None:
    mid = uuid4()
    sid = uuid4()
    row = {'id': mid, 'session_id': sid, 'role': 'user', 'content': 'Hi', 'sources': None}
    pool = _make_pool(fetchrow=row)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await create_message(sid, 'user', 'Hi')
    assert result['role'] == 'user'
    assert result['sources'] is None


async def test_create_message_with_sources() -> None:
    mid = uuid4()
    sid = uuid4()
    sources = [{'url': 'https://x.com', 'title': 'X', 'score': 0.9}]
    row = {'id': mid, 'session_id': sid, 'role': 'assistant', 'content': 'Hi', 'sources': None}
    pool = _make_pool(fetchrow=row)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await create_message(sid, 'assistant', 'Hi', sources)
    assert result['id'] == mid


# ── delete_message ────────────────────────────────────────────────────────────

async def test_delete_message() -> None:
    pool = _make_pool()
    mid = uuid4()
    with patch('app.db.sessions.get_pool', return_value=pool):
        await delete_message(mid)
    pool.execute.assert_called_once()


# ── list_messages ─────────────────────────────────────────────────────────────

async def test_list_messages_empty() -> None:
    pool = _make_pool(fetch=[])
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await list_messages(uuid4())
    assert result == []


async def test_list_messages_returns_dicts() -> None:
    rows = [{'id': uuid4(), 'role': 'user'}, {'id': uuid4(), 'role': 'assistant'}]
    pool = _make_pool(fetch=rows)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await list_messages(uuid4())
    assert len(result) == 2


# ── search_chunks ─────────────────────────────────────────────────────────────

async def test_search_chunks_empty_source_ids_returns_empty() -> None:
    pool = _make_pool()
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await search_chunks([0.1, 0.2], [])
    assert result == []
    pool.fetch.assert_not_called()


async def test_search_chunks_with_source_ids() -> None:
    sid = uuid4()
    rows = [{'url': 'https://x.com', 'title': 'X', 'content': 'text', 'score': 0.9}]
    pool = _make_pool(fetch=rows)
    with patch('app.db.sessions.get_pool', return_value=pool):
        result = await search_chunks([0.1] * 4, [sid])
    assert len(result) == 1
    assert result[0]['url'] == 'https://x.com'


async def test_search_chunks_rejects_nan_embedding() -> None:
    pool = _make_pool()
    with patch('app.db.sessions.get_pool', return_value=pool):
        with pytest.raises(EmbeddingError, match='non-finite'):
            await search_chunks([float('nan')], [uuid4()])


async def test_search_chunks_rejects_inf_embedding() -> None:
    pool = _make_pool()
    with patch('app.db.sessions.get_pool', return_value=pool):
        with pytest.raises(EmbeddingError, match='non-finite'):
            await search_chunks([float('inf'), 0.1], [uuid4()])
