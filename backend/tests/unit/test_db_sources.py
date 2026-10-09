"""Tests for app/db/sources.py — all DB calls are mocked."""
import math
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.sources import (
    _fmt_embedding,
    create_source,
    delete_chunks_for_source,
    delete_source,
    get_source,
    insert_chunk,
    list_sources,
    replace_chunks_for_source,
    set_source_indexing_if_idle,
    update_source_status,
)
from app.exceptions import EmbeddingError


def _make_pool(fetchrow=None, fetch=None, execute_return='DELETE 0'):
    """Return a mock asyncpg pool."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow)
    pool.fetch = AsyncMock(return_value=fetch or [])
    pool.execute = AsyncMock(return_value=execute_return)

    # pool.acquire() is an async context manager returning a conn
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


# ── _fmt_embedding ────────────────────────────────────────────────────────────

def test_fmt_embedding_basic() -> None:
    assert _fmt_embedding([1.0, 2.0, 3.0]) == '[1.0,2.0,3.0]'


def test_fmt_embedding_empty() -> None:
    assert _fmt_embedding([]) == '[]'


# ── create_source ─────────────────────────────────────────────────────────────

async def test_create_source_returns_dict() -> None:
    row = {'id': uuid4(), 'name': 'Docs', 'base_url': 'https://x.com/', 'description': None,
           'status': 'pending', 'chunk_count': 0, 'error_msg': None}
    pool = _make_pool(fetchrow=row)
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await create_source('Docs', 'https://x.com/', None)
    assert result['name'] == 'Docs'


# ── get_source ────────────────────────────────────────────────────────────────

async def test_get_source_found() -> None:
    sid = uuid4()
    row = {'id': sid}
    pool = _make_pool(fetchrow=row)
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await get_source(sid)
    assert result == {'id': sid}


async def test_get_source_not_found() -> None:
    pool = _make_pool(fetchrow=None)
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await get_source(uuid4())
    assert result is None


# ── list_sources ──────────────────────────────────────────────────────────────

async def test_list_sources_empty() -> None:
    pool = _make_pool(fetch=[])
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await list_sources()
    assert result == []


async def test_list_sources_returns_dicts() -> None:
    rows = [{'id': uuid4(), 'name': 'A'}, {'id': uuid4(), 'name': 'B'}]
    pool = _make_pool(fetch=rows)
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await list_sources()
    assert len(result) == 2
    assert result[0]['name'] == 'A'


# ── update_source_status ──────────────────────────────────────────────────────

async def test_update_source_status_with_chunk_count() -> None:
    pool = _make_pool()
    sid = uuid4()
    with patch('app.db.sources.get_pool', return_value=pool):
        await update_source_status(sid, 'ready', chunk_count=42)
    pool.execute.assert_called_once()
    call_args = pool.execute.call_args[0]
    assert 'chunk_count' in call_args[0]


async def test_update_source_status_without_chunk_count() -> None:
    pool = _make_pool()
    sid = uuid4()
    with patch('app.db.sources.get_pool', return_value=pool):
        await update_source_status(sid, 'error', error_msg='failed')
    pool.execute.assert_called_once()
    call_args = pool.execute.call_args[0]
    assert 'chunk_count' not in call_args[0]


# ── set_source_indexing_if_idle ───────────────────────────────────────────────

async def test_set_source_indexing_if_idle_success() -> None:
    pool = _make_pool(execute_return='UPDATE 1')
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await set_source_indexing_if_idle(uuid4())
    assert result is True


async def test_set_source_indexing_if_idle_already_indexing() -> None:
    pool = _make_pool(execute_return='UPDATE 0')
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await set_source_indexing_if_idle(uuid4())
    assert result is False


# ── delete_source ─────────────────────────────────────────────────────────────

async def test_delete_source_found() -> None:
    pool = _make_pool(execute_return='DELETE 1')
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await delete_source(uuid4())
    assert result is True


async def test_delete_source_not_found() -> None:
    pool = _make_pool(execute_return='DELETE 0')
    with patch('app.db.sources.get_pool', return_value=pool):
        result = await delete_source(uuid4())
    assert result is False


# ── delete_chunks_for_source ──────────────────────────────────────────────────

async def test_delete_chunks_for_source() -> None:
    pool = _make_pool()
    sid = uuid4()
    with patch('app.db.sources.get_pool', return_value=pool):
        await delete_chunks_for_source(sid)
    pool.execute.assert_called_once()


# ── insert_chunk ──────────────────────────────────────────────────────────────

async def test_insert_chunk_success() -> None:
    pool = _make_pool()
    with patch('app.db.sources.get_pool', return_value=pool):
        await insert_chunk(uuid4(), 'https://x.com', 'Title', 'Content here', [0.1] * 4)
    pool.execute.assert_called_once()


async def test_insert_chunk_rejects_nan_embedding() -> None:
    pool = _make_pool()
    with patch('app.db.sources.get_pool', return_value=pool):
        with pytest.raises(EmbeddingError, match='non-finite'):
            await insert_chunk(uuid4(), 'https://x.com', None, 'text', [float('nan')])


async def test_insert_chunk_rejects_inf_embedding() -> None:
    pool = _make_pool()
    with patch('app.db.sources.get_pool', return_value=pool):
        with pytest.raises(EmbeddingError, match='non-finite'):
            await insert_chunk(uuid4(), 'https://x.com', None, 'text', [float('inf')])


# ── replace_chunks_for_source ─────────────────────────────────────────────────

async def test_replace_chunks_for_source_empty_chunks() -> None:
    pool = _make_pool()
    sid = uuid4()
    with patch('app.db.sources.get_pool', return_value=pool):
        await replace_chunks_for_source(sid, [])
    # Only the DELETE should be called
    pool._mock_conn.execute.assert_called_once()


async def test_replace_chunks_for_source_with_chunks() -> None:
    pool = _make_pool()
    sid = uuid4()
    chunks = [
        ('https://x.com/a', 'Title A', 'content a', [0.1] * 4),
        ('https://x.com/b', None, 'content b', [0.2] * 4),
    ]
    with patch('app.db.sources.get_pool', return_value=pool):
        await replace_chunks_for_source(sid, chunks)
    # 1 DELETE + 2 INSERTs
    assert pool._mock_conn.execute.call_count == 3


async def test_replace_chunks_rejects_nan_embedding() -> None:
    pool = _make_pool()
    sid = uuid4()
    chunks = [('https://x.com', None, 'text', [float('nan')])]
    with patch('app.db.sources.get_pool', return_value=pool):
        with pytest.raises(EmbeddingError, match='non-finite'):
            await replace_chunks_for_source(sid, chunks)
