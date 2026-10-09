"""Tests for app/db/migrate.py — run_migrations with mocked asyncpg."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_conn(applied_versions: list[str] | None = None):
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(
        return_value=[{'version': v} for v in (applied_versions or [])]
    )
    mock_conn.close = AsyncMock()

    mock_txn = MagicMock()
    mock_txn.__aenter__ = AsyncMock(return_value=None)
    mock_txn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_txn)
    return mock_conn


def _fake_file(stem: str, sql: str = 'SELECT 1;'):
    f = MagicMock()
    f.stem = stem
    f.read_text = MagicMock(return_value=sql)
    return f


async def test_run_migrations_applies_new_migration() -> None:
    from app.db.migrate import run_migrations

    conn = _make_conn(applied_versions=[])
    migration_file = _fake_file('001_init', 'CREATE TABLE t (id SERIAL);')

    with (
        patch('app.db.migrate.asyncpg.connect', AsyncMock(return_value=conn)),
        patch('app.db.migrate.MIGRATIONS_DIR') as mock_dir,
    ):
        mock_dir.glob.return_value = [migration_file]
        await run_migrations()

    conn.close.assert_awaited_once()
    # execute calls: CREATE schema_migrations + migration SQL + INSERT version
    assert conn.execute.await_count >= 3


async def test_run_migrations_skips_already_applied() -> None:
    from app.db.migrate import run_migrations

    conn = _make_conn(applied_versions=['001_init'])
    migration_file = _fake_file('001_init')

    with (
        patch('app.db.migrate.asyncpg.connect', AsyncMock(return_value=conn)),
        patch('app.db.migrate.MIGRATIONS_DIR') as mock_dir,
    ):
        mock_dir.glob.return_value = [migration_file]
        await run_migrations()

    # Only the CREATE TABLE schema_migrations execute call, migration is skipped
    assert conn.execute.await_count == 1
    conn.close.assert_awaited_once()


async def test_run_migrations_no_files_returns_early() -> None:
    from app.db.migrate import run_migrations

    conn = _make_conn(applied_versions=[])

    with (
        patch('app.db.migrate.asyncpg.connect', AsyncMock(return_value=conn)),
        patch('app.db.migrate.MIGRATIONS_DIR') as mock_dir,
    ):
        mock_dir.glob.return_value = []
        await run_migrations()

    assert conn.execute.await_count == 1  # only CREATE TABLE schema_migrations
    conn.close.assert_awaited_once()


async def test_run_migrations_closes_on_exception() -> None:
    from app.db.migrate import run_migrations

    conn = _make_conn()
    conn.execute = AsyncMock(side_effect=RuntimeError('db error'))

    with (
        patch('app.db.migrate.asyncpg.connect', AsyncMock(return_value=conn)),
    ):
        with pytest.raises(RuntimeError, match='db error'):
            await run_migrations()

    conn.close.assert_awaited_once()
