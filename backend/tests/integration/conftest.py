from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.connection import close_db_pool, init_db_pool
from app.main import app

MOCK_EMBEDDING = [0.1] * 768
MOCK_RESPONSE = 'This is a helpful answer about the documentation.'


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # ASGITransport does not trigger the ASGI lifespan — initialize the pool manually.
    await init_db_pool()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as ac:
            yield ac
    finally:
        await close_db_pool()


@pytest.fixture
def mock_ollama() -> AsyncGenerator[AsyncMock, None]:
    with patch('app.services.retrieval.ollama_client') as mock:
        mock.embed = AsyncMock(return_value=MOCK_EMBEDDING)
        yield mock


@pytest.fixture
def mock_anthropic() -> AsyncGenerator[AsyncMock, None]:
    with patch('app.services.chat.anthropic_client') as mock:
        mock.complete = AsyncMock(return_value=MOCK_RESPONSE)
        yield mock
