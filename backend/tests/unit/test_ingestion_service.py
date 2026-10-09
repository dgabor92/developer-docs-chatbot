from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
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
    # Error message is intentionally generic to avoid leaking internal details
    assert calls[1].kwargs.get('error_msg') == 'Ingestion failed'


@pytest.mark.asyncio
async def test_ingest_source_replaces_chunks_atomically() -> None:
    from app.services.ingestion import IngestionService

    source_id = uuid4()
    service = IngestionService()

    fake_page = MagicMock()
    fake_page.content = 'Short page content for testing.'
    fake_page.url = 'https://docs.example.com/page'
    fake_page.title = 'Page'

    with (
        patch('app.services.ingestion.sources_db') as mock_db,
        patch('app.services.ingestion.ollama_client') as mock_ollama,
        patch.object(service, '_crawl', new=AsyncMock(return_value=[fake_page])),
    ):
        mock_db.update_source_status = AsyncMock()
        mock_db.replace_chunks_for_source = AsyncMock()
        mock_ollama.embed = AsyncMock(return_value=[0.1] * 768)

        await service.ingest_source(source_id, 'https://docs.example.com/')

    # replace_chunks_for_source must be called exactly once with the source_id
    mock_db.replace_chunks_for_source.assert_called_once()
    call_source_id, call_chunks = mock_db.replace_chunks_for_source.call_args.args
    assert call_source_id == source_id
    # Each chunk tuple is (url, title, content, embedding)
    assert len(call_chunks) > 0
    assert call_chunks[0][0] == fake_page.url
    assert call_chunks[0][1] == fake_page.title


# ── _is_safe_redirect ─────────────────────────────────────────────────────────

async def test_is_safe_redirect_blocks_localhost() -> None:
    from app.services.ingestion import IngestionService
    assert not await IngestionService._is_safe_redirect('http://localhost/path')


async def test_is_safe_redirect_blocks_zero_addr() -> None:
    from app.services.ingestion import IngestionService
    assert not await IngestionService._is_safe_redirect('http://0.0.0.0/path')


async def test_is_safe_redirect_blocks_empty_hostname() -> None:
    from app.services.ingestion import IngestionService
    assert not await IngestionService._is_safe_redirect('file:///etc/passwd')


async def test_is_safe_redirect_blocks_private_ip_via_dns() -> None:
    from app.services.ingestion import IngestionService
    dns_result = [(None, None, None, None, ('192.168.1.1', 0))]
    with patch('app.services.ingestion.asyncio.to_thread', AsyncMock(return_value=dns_result)):
        result = await IngestionService._is_safe_redirect('http://internal.corp/')
    assert not result


async def test_is_safe_redirect_blocks_loopback_ip_via_dns() -> None:
    from app.services.ingestion import IngestionService
    dns_result = [(None, None, None, None, ('127.0.0.1', 0))]
    with patch('app.services.ingestion.asyncio.to_thread', AsyncMock(return_value=dns_result)):
        result = await IngestionService._is_safe_redirect('http://loopback.example/')
    assert not result


async def test_is_safe_redirect_blocks_unresolvable_host() -> None:
    from app.services.ingestion import IngestionService
    with patch('app.services.ingestion.asyncio.to_thread', AsyncMock(side_effect=OSError('no route'))):
        result = await IngestionService._is_safe_redirect('http://nonexistent.local/')
    assert not result


async def test_is_safe_redirect_allows_public_ip() -> None:
    from app.services.ingestion import IngestionService
    dns_result = [(None, None, None, None, ('8.8.8.8', 0))]
    with patch('app.services.ingestion.asyncio.to_thread', AsyncMock(return_value=dns_result)):
        result = await IngestionService._is_safe_redirect('http://example.com/')
    assert result


# ── _crawl ────────────────────────────────────────────────────────────────────

_CRAWL_HTML = """
<html>
<head><title>Docs Home</title></head>
<body>
  <main>
    <h1>Getting Started</h1>
    <p>Welcome to the documentation. This is a long enough paragraph to pass the minimum content threshold required by the scraper for extraction.</p>
  </main>
</body>
</html>
"""


def _mock_200(html: str = _CRAWL_HTML, headers: dict | None = None):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.text = html
    r.headers = headers or {}
    return r


def _mock_client(response=None, side_effect=None):
    client = AsyncMock()
    if side_effect:
        client.get = AsyncMock(side_effect=side_effect)
    else:
        client.get = AsyncMock(return_value=response or _mock_200())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


async def test_crawl_returns_pages_on_200() -> None:
    from app.services.ingestion import IngestionService
    service = IngestionService()

    mock_client = _mock_client()
    with (
        patch('app.services.ingestion.httpx.AsyncClient', return_value=mock_client),
        patch('app.services.ingestion.asyncio.sleep', AsyncMock()),
    ):
        pages = await service._crawl('https://example.com/docs')

    assert len(pages) >= 1
    assert pages[0].title == 'Getting Started'


async def test_crawl_handles_http_error_gracefully() -> None:
    from app.services.ingestion import IngestionService
    service = IngestionService()

    mock_client = _mock_client(side_effect=httpx.HTTPError('timeout'))
    with (
        patch('app.services.ingestion.httpx.AsyncClient', return_value=mock_client),
        patch('app.services.ingestion.asyncio.sleep', AsyncMock()),
    ):
        pages = await service._crawl('https://example.com/docs')

    assert pages == []


async def test_crawl_handles_http_status_error() -> None:
    from app.services.ingestion import IngestionService
    service = IngestionService()

    mock_resp = _mock_200()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError('404', request=MagicMock(), response=MagicMock())
    )
    mock_client = _mock_client(response=mock_resp)
    with (
        patch('app.services.ingestion.httpx.AsyncClient', return_value=mock_client),
        patch('app.services.ingestion.asyncio.sleep', AsyncMock()),
    ):
        pages = await service._crawl('https://example.com/docs')

    assert pages == []


async def test_crawl_blocks_ssrf_redirect() -> None:
    from app.services.ingestion import IngestionService
    service = IngestionService()

    redirect_resp = MagicMock()
    redirect_resp.status_code = 301
    redirect_resp.headers = {'location': 'http://169.254.169.254/metadata'}
    redirect_resp.raise_for_status = MagicMock()
    redirect_resp.text = ''

    mock_client = _mock_client(response=redirect_resp)
    with (
        patch('app.services.ingestion.httpx.AsyncClient', return_value=mock_client),
        patch('app.services.ingestion.asyncio.sleep', AsyncMock()),
        patch(
            'app.services.ingestion.IngestionService._is_safe_redirect',
            AsyncMock(return_value=False),
        ),
    ):
        pages = await service._crawl('https://example.com/docs')

    assert pages == []
