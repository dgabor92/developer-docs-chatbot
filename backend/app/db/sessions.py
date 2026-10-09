import json
import math
from typing import Any
from uuid import UUID

import structlog

from app.db.connection import get_pool
from app.exceptions import EmbeddingError

logger = structlog.get_logger()


async def create_session(source_ids: list[UUID]) -> dict[str, Any]:
    pool = get_pool()
    row = await pool.fetchrow(
        "INSERT INTO sessions (source_ids) VALUES ($1::uuid[]) RETURNING *",
        source_ids,
    )
    return dict(row)


async def get_session(session_id: UUID) -> dict[str, Any] | None:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
    return dict(row) if row else None


async def list_sessions() -> list[dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM sessions ORDER BY updated_at DESC")
    return [dict(row) for row in rows]


async def delete_session(session_id: UUID) -> bool:
    pool = get_pool()
    result = await pool.execute("DELETE FROM sessions WHERE id = $1", session_id)
    return str(result) == "DELETE 1"


async def update_session_title(session_id: UUID, title: str) -> None:
    pool = get_pool()
    await pool.execute(
        "UPDATE sessions SET title = $1, updated_at = now() WHERE id = $2",
        title,
        session_id,
    )


async def create_message(
    session_id: UUID,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    sources_json = json.dumps(sources) if sources is not None else None
    async with pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """
            INSERT INTO messages (session_id, role, content, sources)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING *
            """,
            session_id,
            role,
            content,
            sources_json,
        )
        await conn.execute(
            "UPDATE sessions SET updated_at = now() WHERE id = $1",
            session_id,
        )
    result = dict(row)
    if result.get("sources") is None:
        result["sources"] = None
    return result


async def delete_message(message_id: UUID) -> None:
    pool = get_pool()
    await pool.execute("DELETE FROM messages WHERE id = $1", message_id)


async def list_messages(session_id: UUID) -> list[dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT * FROM messages WHERE session_id = $1 ORDER BY created_at",
        session_id,
    )
    return [dict(row) for row in rows]


async def search_chunks(
    embedding: list[float],
    source_ids: list[UUID],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not all(math.isfinite(f) for f in embedding):
        raise EmbeddingError("Query embedding contains non-finite values (NaN/Inf)")

    pool = get_pool()
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"

    if source_ids:
        rows = await pool.fetch(
            """
            SELECT url, title, content,
                   1 - (embedding <=> $1::vector) AS score
            FROM chunks
            WHERE source_id = ANY($2::uuid[])
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            embedding_str,
            source_ids,
            top_k,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT url, title, content,
                   1 - (embedding <=> $1::vector) AS score
            FROM chunks
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding_str,
            top_k,
        )

    return [dict(row) for row in rows]
