import os

import pytest

os.environ.setdefault('DATABASE_URL', 'postgresql://chatbot:chatbot@localhost/chatbot')
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-unit-test-placeholder')


@pytest.fixture
def anyio_backend() -> str:
    return 'asyncio'
