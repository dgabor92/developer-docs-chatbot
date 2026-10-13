from dataclasses import dataclass
from typing import Any
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
        top_k: int = 8,
    ) -> list[ChunkResult]:
        try:
            embedding = await ollama_client.embed(query)
        except EmbeddingError as e:
            raise RetrievalError(f"Failed to embed query: {e}") from e

        # Fetch more candidates so diversity filtering still yields top_k results
        rows = await search_chunks(embedding, source_ids, top_k * 4)

        # Diversity: keep at most 2 chunks per URL so one page can't crowd out others
        url_counts: dict[str, int] = {}
        diverse: list[dict[str, Any]] = []
        for row in rows:
            url = row["url"]
            if url_counts.get(url, 0) < 2:
                diverse.append(row)
                url_counts[url] = url_counts.get(url, 0) + 1
            if len(diverse) == top_k:
                break

        logger.info(
            "retrieval_search_done",
            query_length=len(query),
            chunks_found=len(diverse),
            filtered_by_sources=bool(source_ids),
        )

        return [
            ChunkResult(
                url=row["url"],
                title=row["title"],
                content=row["content"],
                score=float(row["score"]),
            )
            for row in diverse
        ]


retrieval_service = RetrievalService()
