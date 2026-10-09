from dataclasses import dataclass
from uuid import UUID

import structlog

from app.clients.ollama import ollama_client
from app.db.sessions import search_chunks
from app.exceptions import EmbeddingError, RetrievalError

logger = structlog.get_logger()


@dataclass
class ChunkResult:
    url: str
    title: str | None
    content: str
    score: float


class RetrievalService:
    async def search(
        self,
        query: str,
        source_ids: list[UUID],
        top_k: int = 5,
    ) -> list[ChunkResult]:
        try:
            embedding = await ollama_client.embed(query)
        except EmbeddingError as e:
            raise RetrievalError(f"Failed to embed query: {e}") from e

        rows = await search_chunks(embedding, source_ids, top_k)

        logger.info(
            "retrieval_search_done",
            query_length=len(query),
            chunks_found=len(rows),
            filtered_by_sources=bool(source_ids),
        )

        return [
            ChunkResult(
                url=row["url"],
                title=row["title"],
                content=row["content"],
                score=float(row["score"]),
            )
            for row in rows
        ]


retrieval_service = RetrievalService()
