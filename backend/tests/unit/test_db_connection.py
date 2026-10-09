"""Tests for app/db/connection.py."""
from unittest.mock import AsyncMock, patch

import pytest

import app.db.connection as conn_module
from app.db.connection import close_db_pool, get_pool


def test_get_pool_raises_when_not_initialized() -> None:
    original = conn_module._pool
    conn_module._pool = None
    try:
        with pytest.raises(RuntimeError, match='not initialized'):
            get_pool()
    finally:
        conn_module._pool = original


async def test_init_and_close_pool() -> None:
    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()

    original = conn_module._pool
    try:
        with patch('app.db.connection.asyncpg.create_pool', AsyncMock(return_value=mock_pool)):
            await conn_module.init_db_pool()
            assert conn_module._pool is mock_pool
            assert get_pool() is mock_pool

            await close_db_pool()
            mock_pool.close.assert_called_once()
            assert conn_module._pool is None
    finally:
        conn_module._pool = original


async def test_close_pool_noop_when_not_initialized() -> None:
    original = conn_module._pool
    conn_module._pool = None
    try:
        await close_db_pool()  # should not raise
    finally:
        conn_module._pool = original
