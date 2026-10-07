"""Integration tests for the sources API — require Docker PostgreSQL to be running."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_source_rejects_invalid_url(client: AsyncClient) -> None:
    for bad_url in ('not-a-url', 'file:///etc/passwd', 'javascript:alert(1)', ''):
        response = await client.post(
            '/api/sources',
            json={'name': 'Test', 'base_url': bad_url},
        )
        assert response.status_code == 422, f'Expected 422 for: {bad_url!r}'


@pytest.mark.asyncio
async def test_create_source_accepts_valid_http_url(client: AsyncClient) -> None:
    from unittest.mock import patch

    with patch('app.services.ingestion.ingestion_service.ingest_source'):
        response = await client.post(
            '/api/sources',
            json={'name': 'Test Docs', 'base_url': 'https://docs.example.com/'},
        )

    assert response.status_code == 201
    source_id = response.json()['id']

    await client.delete(f'/api/sources/{source_id}')


@pytest.mark.asyncio
async def test_create_source_duplicate_returns_409(client: AsyncClient) -> None:
    from unittest.mock import patch

    url = 'https://docs.example-dedup-test.com/'

    with patch('app.services.ingestion.ingestion_service.ingest_source'):
        first = await client.post(
            '/api/sources',
            json={'name': 'First', 'base_url': url},
        )
        assert first.status_code == 201

        second = await client.post(
            '/api/sources',
            json={'name': 'Second', 'base_url': url},
        )
        assert second.status_code == 409

    await client.delete(f'/api/sources/{first.json()["id"]}')


@pytest.mark.asyncio
async def test_reindex_returns_indexing_status(client: AsyncClient) -> None:
    from unittest.mock import patch

    with patch('app.services.ingestion.ingestion_service.ingest_source'):
        create = await client.post(
            '/api/sources',
            json={'name': 'Reindex Test', 'base_url': 'https://docs.reindex-test.com/'},
        )
        assert create.status_code == 201
        source_id = create.json()['id']

        reindex = await client.post(f'/api/sources/{source_id}/reindex')

    assert reindex.status_code == 200
    assert reindex.json()['status'] == 'indexing'

    await client.delete(f'/api/sources/{source_id}')


@pytest.mark.asyncio
async def test_get_source_not_found(client: AsyncClient) -> None:
    response = await client.get('/api/sources/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_source_not_found(client: AsyncClient) -> None:
    response = await client.delete('/api/sources/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404
