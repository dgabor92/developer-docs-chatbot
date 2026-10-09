"""Tests for app/clients/anthropic.py and app/clients/ollama.py."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.anthropic import AnthropicClient
from app.clients.ollama import OllamaClient
from app.exceptions import ChatError, EmbeddingError


# ── AnthropicClient ───────────────────────────────────────────────────────────

class TestAnthropicClientIsConfigured:
    def _client_with_key(self, key: str) -> AnthropicClient:
        with patch('app.clients.anthropic.settings') as mock_settings:
            mock_settings.anthropic_api_key = key
            mock_settings.llm_model = 'claude-haiku-4-5-20251001'
            return AnthropicClient()

    def test_configured_with_valid_key(self) -> None:
        c = self._client_with_key('sk-ant-abc123')
        with patch.object(c, '_client', MagicMock()):
            with patch('app.clients.anthropic.settings') as s:
                s.anthropic_api_key = 'sk-ant-abc123'
                assert c.is_configured() is True

    def test_not_configured_with_wrong_prefix(self) -> None:
        c = self._client_with_key('sk-other-abc')
        with patch('app.clients.anthropic.settings') as s:
            s.anthropic_api_key = 'sk-other-abc'
            assert c.is_configured() is False

    def test_not_configured_with_empty_key(self) -> None:
        c = self._client_with_key('')
        with patch('app.clients.anthropic.settings') as s:
            s.anthropic_api_key = ''
            assert c.is_configured() is False


class TestAnthropicClientComplete:
    def _make_client(self) -> AnthropicClient:
        with patch('app.clients.anthropic.settings') as s:
            s.anthropic_api_key = 'sk-ant-test'
            s.llm_model = 'claude-haiku-4-5-20251001'
            return AnthropicClient()

    async def test_complete_returns_text(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='Hello world')]
        client._client = MagicMock()
        client._client.messages.create = AsyncMock(return_value=mock_response)
        result = await client.complete('system', [{'role': 'user', 'content': 'hi'}])
        assert result == 'Hello world'

    async def test_complete_raises_chat_error_on_api_error(self) -> None:
        import anthropic
        client = self._make_client()
        client._client = MagicMock()
        client._client.messages.create = AsyncMock(
            side_effect=anthropic.APIError(message='bad request', request=MagicMock(), body=None)
        )
        with pytest.raises(ChatError):
            await client.complete('system', [{'role': 'user', 'content': 'hi'}])


class TestAnthropicClientStream:
    def _make_client(self) -> AnthropicClient:
        with patch('app.clients.anthropic.settings') as s:
            s.anthropic_api_key = 'sk-ant-test'
            s.llm_model = 'claude-haiku-4-5-20251001'
            return AnthropicClient()

    async def test_stream_yields_tokens(self) -> None:
        import anthropic
        client = self._make_client()

        async def fake_text_stream():
            yield 'Hello '
            yield 'world'

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_stream_ctx.text_stream = fake_text_stream()

        client._client = MagicMock()
        client._client.messages.stream = MagicMock(return_value=mock_stream_ctx)

        tokens = []
        async for token in client.stream('sys', [{'role': 'user', 'content': 'hi'}]):
            tokens.append(token)
        assert tokens == ['Hello ', 'world']

    async def test_stream_raises_chat_error_on_api_error(self) -> None:
        import anthropic
        client = self._make_client()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(
            side_effect=anthropic.APIError(message='fail', request=MagicMock(), body=None)
        )
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        client._client = MagicMock()
        client._client.messages.stream = MagicMock(return_value=mock_stream_ctx)

        with pytest.raises(ChatError):
            async for _ in client.stream('sys', [{'role': 'user', 'content': 'hi'}]):
                pass


# ── OllamaClient ──────────────────────────────────────────────────────────────

class TestOllamaClientEmbed:
    def _make_client(self) -> OllamaClient:
        with patch('app.clients.ollama.settings') as s:
            s.ollama_url = 'http://localhost:11434'
            s.embedding_model = 'nomic-embed-text'
            return OllamaClient()

    async def test_embed_returns_vector(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={'embedding': [0.1, 0.2, 0.3]})
        client._client = MagicMock()
        client._client.post = AsyncMock(return_value=mock_response)
        result = await client.embed('hello world')
        assert result == [0.1, 0.2, 0.3]

    async def test_embed_raises_on_missing_field(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={'other': 'data'})
        client._client = MagicMock()
        client._client.post = AsyncMock(return_value=mock_response)
        with pytest.raises(EmbeddingError, match='missing embedding field'):
            await client.embed('hello')

    async def test_embed_raises_on_http_error(self) -> None:
        import httpx
        client = self._make_client()
        client._client = MagicMock()
        client._client.post = AsyncMock(side_effect=httpx.ConnectError('refused'))
        with pytest.raises(EmbeddingError):
            await client.embed('hello')


class TestOllamaClientIsAvailable:
    def _make_client(self) -> OllamaClient:
        with patch('app.clients.ollama.settings') as s:
            s.ollama_url = 'http://localhost:11434'
            s.embedding_model = 'nomic-embed-text'
            return OllamaClient()

    async def test_is_available_true(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        client._client = MagicMock()
        client._client.get = AsyncMock(return_value=mock_response)
        assert await client.is_available() is True

    async def test_is_available_false_on_non_200(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 503
        client._client = MagicMock()
        client._client.get = AsyncMock(return_value=mock_response)
        assert await client.is_available() is False

    async def test_is_available_false_on_http_error(self) -> None:
        import httpx
        client = self._make_client()
        client._client = MagicMock()
        client._client.get = AsyncMock(side_effect=httpx.ConnectError('refused'))
        assert await client.is_available() is False

    async def test_aclose(self) -> None:
        client = self._make_client()
        client._client = MagicMock()
        client._client.aclose = AsyncMock()
        await client.aclose()
        client._client.aclose.assert_called_once()
