import math
from typing import Any
from uuid import UUID

import structlog

from app.db.connection import get_pool
from app.exceptions import EmbeddingError

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
    return dict(row)


async def get_source(source_id: UUID) -> dict[str, Any] | None:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM sources WHERE id = $1", source_id)
    return dict(row) if row else None


async def list_sources() -> list[dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM sources ORDER BY created_at DESC")
    return [dict(row) for row in rows]


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


async def set_source_indexing_if_idle(source_id: UUID) -> bool:
    """Atomically set status to 'indexing' only if not already indexing.

    Returns True if the update succeeded (i.e. source was idle), False if it was already indexing.
    """
    pool = get_pool()
    sql = (
        "UPDATE sources SET status='indexing', updated_at=now()"
        " WHERE id=$1 AND status != 'indexing'"
    )
    result = await pool.execute(sql, source_id)
    return str(result) == "UPDATE 1"


async def delete_source(source_id: UUID) -> bool:
    pool = get_pool()
    result = await pool.execute("DELETE FROM sources WHERE id = $1", source_id)
    return str(result) == "DELETE 1"


async def delete_chunks_for_source(source_id: UUID) -> None:
    pool = get_pool()
    await pool.execute("DELETE FROM chunks WHERE source_id = $1", source_id)


async def insert_chunk(
    source_id: UUID,
    url: str,
    title: str | None,
    content: str,
    embedding: list[float],
) -> None:
    if not all(math.isfinite(f) for f in embedding):
        raise EmbeddingError(f"Embedding for {url} contains non-finite values (NaN/Inf)")

    pool = get_pool()
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
    token_count = len(content) // 4
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


async def replace_chunks_for_source(
    source_id: UUID,
    chunks: list[tuple[str, str | None, str, list[float]]],
) -> None:
    """Atomically delete all existing chunks and insert the new ones in a single transaction."""
    pool = get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("DELETE FROM chunks WHERE source_id = $1", source_id)
        for url, title, content, embedding in chunks:
            if not all(math.isfinite(f) for f in embedding):
                raise EmbeddingError(f"Embedding for {url} contains non-finite values (NaN/Inf)")
            embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
            token_count = len(content) // 4
            await conn.execute(
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
