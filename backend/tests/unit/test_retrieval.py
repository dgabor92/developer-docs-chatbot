from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.exceptions import EmbeddingError, RetrievalError
from app.services.retrieval import ChunkResult, RetrievalService


MOCK_EMBEDDING = [0.1] * 768
MOCK_CHUNKS = [
    {
        'url': 'https://example.com/docs/page1',
        'title': 'Installation',
        'content': 'Install via npm.',
        'score': 0.95,
    },
    {
        'url': 'https://example.com/docs/page2',
        'title': 'Configuration',
        'content': 'Configure your settings.',
        'score': 0.82,
    },
]


@pytest.fixture
def service() -> RetrievalService:
    return RetrievalService()


@pytest.mark.asyncio
async def test_search_returns_chunk_results(service: RetrievalService) -> None:
    with (
        patch('app.services.retrieval.ollama_client') as mock_ollama,
        patch('app.services.retrieval.search_chunks', new_callable=AsyncMock) as mock_search,
    ):
        mock_ollama.embed = AsyncMock(return_value=MOCK_EMBEDDING)
        mock_search.return_value = MOCK_CHUNKS

        results = await service.search('How do I install?', [], top_k=5)

    assert len(results) == 2
    assert isinstance(results[0], ChunkResult)
    assert results[0].url == 'https://example.com/docs/page1'
    assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_search_passes_source_ids(service: RetrievalService) -> None:
    source_id = uuid4()
    with (
        patch('app.services.retrieval.ollama_client') as mock_ollama,
        patch('app.services.retrieval.search_chunks', new_callable=AsyncMock) as mock_search,
    ):
        mock_ollama.embed = AsyncMock(return_value=MOCK_EMBEDDING)
        mock_search.return_value = []

        await service.search('query', [source_id], top_k=3)

        mock_search.assert_called_once_with(MOCK_EMBEDDING, [source_id], 3)


@pytest.mark.asyncio
async def test_search_passes_empty_source_ids(service: RetrievalService) -> None:
    with (
        patch('app.services.retrieval.ollama_client') as mock_ollama,
        patch('app.services.retrieval.search_chunks', new_callable=AsyncMock) as mock_search,
    ):
        mock_ollama.embed = AsyncMock(return_value=MOCK_EMBEDDING)
        mock_search.return_value = []

        await service.search('query', [], top_k=5)

        mock_search.assert_called_once_with(MOCK_EMBEDDING, [], 5)


@pytest.mark.asyncio
async def test_search_raises_retrieval_error_on_embed_failure(service: RetrievalService) -> None:
    with patch('app.services.retrieval.ollama_client') as mock_ollama:
        mock_ollama.embed = AsyncMock(side_effect=EmbeddingError('Ollama is down'))

        with pytest.raises(RetrievalError, match='Failed to embed query'):
            await service.search('query', [])


@pytest.mark.asyncio
async def test_search_returns_empty_on_no_chunks(service: RetrievalService) -> None:
    with (
        patch('app.services.retrieval.ollama_client') as mock_ollama,
        patch('app.services.retrieval.search_chunks', new_callable=AsyncMock) as mock_search,
    ):
        mock_ollama.embed = AsyncMock(return_value=MOCK_EMBEDDING)
        mock_search.return_value = []

        results = await service.search('rare query', [])

    assert results == []
