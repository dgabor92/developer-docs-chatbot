import json
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.connection import close_db_pool, init_db_pool
from app.main import app

MOCK_EMBEDDING = [0.1] * 768
MOCK_TOKENS = ['This is ', 'a helpful ', 'answer about ', 'the documentation.']
MOCK_RESPONSE = ''.join(MOCK_TOKENS)


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
def mock_ollama() -> Generator[AsyncMock, None, None]:
    with patch('app.services.retrieval.ollama_client') as mock:
        mock.embed = AsyncMock(return_value=MOCK_EMBEDDING)
        yield mock


@pytest.fixture
def mock_anthropic() -> Generator[AsyncMock, None, None]:
    async def _mock_stream(*args, **kwargs):
        for token in MOCK_TOKENS:
            yield token

    with patch('app.services.chat.anthropic_client') as mock:
        mock.stream = _mock_stream
        yield mock


def parse_sse(text: str) -> list[dict]:  # type: ignore[type-arg]
    """Parse SSE response text into a list of {event, data} dicts."""
    events = []
    current: dict = {}  # type: ignore[type-arg]
    for line in text.splitlines():
        if line.startswith('event: '):
            current['event'] = line[7:]
        elif line.startswith('data: '):
            current['data'] = json.loads(line[6:])
        elif line == '' and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events
