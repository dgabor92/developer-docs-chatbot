import asyncio
from pathlib import Path

import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger()

MIGRATIONS_DIR = Path(__file__).parent / 'migrations'


async def run_migrations() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        applied = {
            row['version']
            for row in await conn.fetch('SELECT version FROM schema_migrations')
        }

        migration_files = sorted(MIGRATIONS_DIR.glob('*.sql'))
        if not migration_files:
            logger.warning('no_migration_files_found', path=str(MIGRATIONS_DIR))
            return

        for migration_file in migration_files:
            version = migration_file.stem
            if version in applied:
                logger.info('migration_skipped', version=version)
                continue

            sql = migration_file.read_text()
            await conn.execute(sql)
            await conn.execute(
                'INSERT INTO schema_migrations (version) VALUES ($1)',
                version,
            )
            logger.info('migration_applied', version=version)

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(run_migrations())
