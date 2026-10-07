from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import EmbeddingError


@pytest.mark.asyncio
async def test_ingest_source_sets_error_status_on_embed_failure() -> None:
    from app.services.ingestion import IngestionService

    source_id = uuid4()
    service = IngestionService()

    fake_page = MagicMock()
    fake_page.content = 'Some documentation content that will be chunked.'
    fake_page.url = 'https://docs.example.com/page'
    fake_page.title = 'Page Title'

    with (
        patch('app.services.ingestion.sources_db') as mock_db,
        patch('app.services.ingestion.ollama_client') as mock_ollama,
        patch.object(service, '_crawl', new=AsyncMock(return_value=[fake_page])),
    ):
        mock_db.update_source_status = AsyncMock()
        mock_db.delete_chunks_for_source = AsyncMock()
        mock_db.insert_chunk = AsyncMock()
        mock_ollama.embed = AsyncMock(side_effect=EmbeddingError('Ollama timed out'))

        await service.ingest_source(source_id, 'https://docs.example.com/')

    # First call: 'indexing', second call: 'error'
    calls = mock_db.update_source_status.call_args_list
    assert calls[0].args == (source_id, 'indexing')
    assert calls[1].args[1] == 'error'
    assert 'Ollama timed out' in calls[1].kwargs.get('error_msg', calls[1].args[2] if len(calls[1].args) > 2 else '')


@pytest.mark.asyncio
async def test_ingest_source_deletes_chunks_before_inserting() -> None:
    from app.services.ingestion import IngestionService

    source_id = uuid4()
    service = IngestionService()

    fake_page = MagicMock()
    fake_page.content = 'Short page.'
    fake_page.url = 'https://docs.example.com/page'
    fake_page.title = 'Page'

    call_order: list[str] = []

    async def track_delete(*args, **kwargs):
        call_order.append('delete')

    async def track_insert(*args, **kwargs):
        call_order.append('insert')

    with (
        patch('app.services.ingestion.sources_db') as mock_db,
        patch('app.services.ingestion.ollama_client') as mock_ollama,
        patch.object(service, '_crawl', new=AsyncMock(return_value=[fake_page])),
    ):
        mock_db.update_source_status = AsyncMock()
        mock_db.delete_chunks_for_source = AsyncMock(side_effect=track_delete)
        mock_db.insert_chunk = AsyncMock(side_effect=track_insert)
        mock_ollama.embed = AsyncMock(return_value=[0.1] * 768)

        await service.ingest_source(source_id, 'https://docs.example.com/')

    assert 'delete' in call_order
    assert call_order.index('delete') < call_order.index('insert')
