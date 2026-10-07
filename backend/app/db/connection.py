import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger()

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
    )
    logger.info('db_pool_initialized')


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info('db_pool_closed')


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError('Database pool is not initialized')
    return _pool
