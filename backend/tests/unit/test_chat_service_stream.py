"""Tests for ChatService.stream_message."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import NotFoundError
from app.services.chat import ChatService
from app.services.retrieval import ChunkResult


def _make_user_msg(session_id=None, msg_id=None):
    return {'id': msg_id or uuid4(), 'session_id': session_id or uuid4(),
            'role': 'user', 'content': 'hi'}


def _make_asst_msg(session_id=None, msg_id=None):
    return {'id': msg_id or uuid4(), 'session_id': session_id or uuid4(),
            'role': 'assistant', 'content': 'Hello world'}


async def _collect_stream(gen):
    events = []
    async for event, data in gen:
        events.append((event, data))
    return events


class TestStreamMessage:
    async def test_raises_not_found_when_session_missing(self) -> None:
        service = ChatService()
        with patch('app.services.chat.get_session', AsyncMock(return_value=None)):
            with pytest.raises(NotFoundError):
                async for _ in service.stream_message(uuid4(), 'hello'):
                    pass

    async def test_yields_tokens_sources_done(self) -> None:
        service = ChatService()
        sess_id = uuid4()
        session = {'id': sess_id, 'source_ids': [uuid4()], 'title': None}
        user_msg = _make_user_msg(session_id=sess_id)
        asst_msg = _make_asst_msg(session_id=sess_id)
        chunk = ChunkResult(url='https://x.com', title='X', content='text', score=0.9)

        async def fake_stream(system, messages, **kw):
            yield 'Hello '
            yield 'world'

        with (
            patch('app.services.chat.get_session', AsyncMock(return_value=session)),
            patch('app.services.chat.create_message', AsyncMock(side_effect=[user_msg, asst_msg])),
            patch('app.services.chat.list_messages', AsyncMock(return_value=[])),
            patch('app.services.chat.update_session_title', AsyncMock()),
            patch('app.services.chat.retrieval_service') as mock_ret,
            patch('app.services.chat.anthropic_client') as mock_ant,
        ):
            mock_ret.search = AsyncMock(return_value=[chunk])
            mock_ant.stream = fake_stream

            events = await _collect_stream(service.stream_message(sess_id, 'hello'))

        event_types = [e for e, _ in events]
        assert 'token' in event_types
        assert 'sources' in event_types
        assert 'done' in event_types

        token_data = [d for e, d in events if e == 'token']
        full = ''.join(t['content'] for t in token_data)
        assert full == 'Hello world'

    async def test_cleans_up_user_message_on_stream_error(self) -> None:
        service = ChatService()
        sess_id = uuid4()
        session = {'id': sess_id, 'source_ids': [], 'title': None}
        user_msg = _make_user_msg(session_id=sess_id)

        async def exploding_stream(system, messages, **kw):
            yield 'partial'
            raise RuntimeError('network error')

        with (
            patch('app.services.chat.get_session', AsyncMock(return_value=session)),
            patch('app.services.chat.create_message', AsyncMock(return_value=user_msg)),
            patch('app.services.chat.delete_message', AsyncMock()) as mock_delete,
            patch('app.services.chat.list_messages', AsyncMock(return_value=[])),
            patch('app.services.chat.retrieval_service') as mock_ret,
            patch('app.services.chat.anthropic_client') as mock_ant,
        ):
            mock_ret.search = AsyncMock(return_value=[])
            mock_ant.stream = exploding_stream

            with pytest.raises(RuntimeError, match='network error'):
                async for _ in service.stream_message(sess_id, 'hello'):
                    pass

        mock_delete.assert_called_once_with(user_msg['id'])

    async def test_sets_session_title_on_first_message(self) -> None:
        service = ChatService()
        sess_id = uuid4()
        session = {'id': sess_id, 'source_ids': [], 'title': None}
        user_msg = _make_user_msg(session_id=sess_id)
        asst_msg = _make_asst_msg(session_id=sess_id)

        async def fake_stream(system, messages, **kw):
            yield 'ok'

        with (
            patch('app.services.chat.get_session', AsyncMock(return_value=session)),
            patch('app.services.chat.create_message', AsyncMock(side_effect=[user_msg, asst_msg])),
            patch('app.services.chat.list_messages', AsyncMock(return_value=[])),
            patch('app.services.chat.update_session_title', AsyncMock()) as mock_title,
            patch('app.services.chat.retrieval_service') as mock_ret,
            patch('app.services.chat.anthropic_client') as mock_ant,
        ):
            mock_ret.search = AsyncMock(return_value=[])
            mock_ant.stream = fake_stream

            await _collect_stream(service.stream_message(sess_id, 'my question'))

        mock_title.assert_called_once()
        assert mock_title.call_args[0][1] == 'my question'

    async def test_does_not_update_title_when_already_set(self) -> None:
        service = ChatService()
        sess_id = uuid4()
        session = {'id': sess_id, 'source_ids': [], 'title': 'Existing Title'}
        user_msg = _make_user_msg(session_id=sess_id)
        asst_msg = _make_asst_msg(session_id=sess_id)

        async def fake_stream(system, messages, **kw):
            yield 'response'

        with (
            patch('app.services.chat.get_session', AsyncMock(return_value=session)),
            patch('app.services.chat.create_message', AsyncMock(side_effect=[user_msg, asst_msg])),
            patch('app.services.chat.list_messages', AsyncMock(return_value=[])),
            patch('app.services.chat.update_session_title', AsyncMock()) as mock_title,
            patch('app.services.chat.retrieval_service') as mock_ret,
            patch('app.services.chat.anthropic_client') as mock_ant,
        ):
            mock_ret.search = AsyncMock(return_value=[])
            mock_ant.stream = fake_stream

            await _collect_stream(service.stream_message(sess_id, 'question'))

        mock_title.assert_not_called()
