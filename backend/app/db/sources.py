from typing import Any
from uuid import UUID

import structlog

from app.db.connection import get_pool

logger = structlog.get_logger()


async def create_source(
    name: str,
    base_url: str,
    description: str | None,
) -> dict[str, Any]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO sources (name, base_url, description)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        name,
        base_url,
        description,
    )
    return dict(row)  # type: ignore[arg-type]


async def get_source(source_id: UUID) -> dict[str, Any] | None:
    pool = get_pool()
    row = await pool.fetchrow('SELECT * FROM sources WHERE id = $1', source_id)
    return dict(row) if row else None  # type: ignore[arg-type]


async def list_sources() -> list[dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch('SELECT * FROM sources ORDER BY created_at DESC')
    return [dict(row) for row in rows]  # type: ignore[arg-type]


async def update_source_status(
    source_id: UUID,
    status: str,
    chunk_count: int | None = None,
    error_msg: str | None = None,
) -> None:
    pool = get_pool()
    if chunk_count is not None:
        await pool.execute(
            """
            UPDATE sources
            SET status = $1, chunk_count = $2, error_msg = $3, updated_at = now()
            WHERE id = $4
            """,
            status,
            chunk_count,
            error_msg,
            source_id,
        )
    else:
        await pool.execute(
            """
            UPDATE sources
            SET status = $1, error_msg = $2, updated_at = now()
            WHERE id = $3
            """,
            status,
            error_msg,
            source_id,
        )


async def delete_source(source_id: UUID) -> bool:
    pool = get_pool()
    result = await pool.execute('DELETE FROM sources WHERE id = $1', source_id)
    return result == 'DELETE 1'


async def insert_chunk(
    source_id: UUID,
    url: str,
    title: str | None,
    content: str,
    embedding: list[float],
) -> None:
    pool = get_pool()
    embedding_str = '[' + ','.join(str(f) for f in embedding) + ']'
    token_count = len(content) // 4  # rough estimate: ~4 chars per token
    await pool.execute(
        """
        INSERT INTO chunks (source_id, url, title, content, token_count, embedding)
        VALUES ($1, $2, $3, $4, $5, $6::vector)
        """,
        source_id,
        url,
        title,
        content,
        token_count,
        embedding_str,
    )
