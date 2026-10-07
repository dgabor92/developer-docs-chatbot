"""Integration tests for the sessions API — require Docker PostgreSQL to be running."""
import pytest
from httpx import AsyncClient

from tests.integration.conftest import MOCK_RESPONSE, parse_sse


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient) -> None:
    response = await client.post('/api/sessions', json={'source_ids': []})
    assert response.status_code == 201
    data = response.json()
    assert 'id' in data
    assert data['source_ids'] == []
    assert data['title'] is None

    await client.delete(f'/api/sessions/{data["id"]}')


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    response = await client.get('/api/sessions')
    assert response.status_code == 200
    ids = [s['id'] for s in response.json()]
    assert session_id in ids

    await client.delete(f'/api/sessions/{session_id}')


@pytest.mark.asyncio
async def test_get_session_with_messages(client: AsyncClient) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    response = await client.get(f'/api/sessions/{session_id}')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == session_id
    assert data['messages'] == []

    await client.delete(f'/api/sessions/{session_id}')


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient) -> None:
    response = await client.get('/api/sessions/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    delete = await client.delete(f'/api/sessions/{session_id}')
    assert delete.status_code == 204

    get = await client.get(f'/api/sessions/{session_id}')
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_not_found(client: AsyncClient) -> None:
    response = await client.delete('/api/sessions/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message_full_rag_pipeline(
    client: AsyncClient,
    mock_ollama: object,
    mock_anthropic: object,
) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    response = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': 'How do I install Tailwind CSS?'},
    )
    assert response.status_code == 200
    assert 'text/event-stream' in response.headers['content-type']

    events = parse_sse(response.text)
    event_types = [e['event'] for e in events]
    assert 'token' in event_types
    assert 'sources' in event_types
    assert 'done' in event_types

    token_events = [e for e in events if e['event'] == 'token']
    full_content = ''.join(e['data']['content'] for e in token_events)
    assert full_content == MOCK_RESPONSE

    done_event = next(e for e in events if e['event'] == 'done')
    assert done_event['data']['session_id'] == session_id

    session = await client.get(f'/api/sessions/{session_id}')
    messages = session.json()['messages']
    assert len(messages) == 2
    assert messages[0]['role'] == 'user'
    assert messages[1]['role'] == 'assistant'
    assert messages[1]['content'] == MOCK_RESPONSE

    await client.delete(f'/api/sessions/{session_id}')


@pytest.mark.asyncio
async def test_send_message_sets_session_title(
    client: AsyncClient,
    mock_ollama: object,
    mock_anthropic: object,
) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    question = 'How do I configure dark mode in Tailwind?'
    response = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': question},
    )
    assert response.status_code == 200
    # Consume the stream so the title write completes
    assert any(e['event'] == 'done' for e in parse_sse(response.text))

    session = await client.get(f'/api/sessions/{session_id}')
    assert session.json()['title'] == question

    await client.delete(f'/api/sessions/{session_id}')


@pytest.mark.asyncio
async def test_send_message_session_not_found(client: AsyncClient) -> None:
    response = await client.post(
        '/api/sessions/00000000-0000-0000-0000-000000000000/messages',
        json={'content': 'Hello'},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_multi_turn_conversation_persists_history(
    client: AsyncClient,
    mock_ollama: object,
    mock_anthropic: object,
) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    r1 = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': 'What is Tailwind CSS?'},
    )
    assert any(e['event'] == 'done' for e in parse_sse(r1.text))

    r2 = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': 'How do I add custom colors?'},
    )
    assert any(e['event'] == 'done' for e in parse_sse(r2.text))

    session = await client.get(f'/api/sessions/{session_id}')
    messages = session.json()['messages']

    assert len(messages) == 4
    assert messages[0]['role'] == 'user'
    assert messages[1]['role'] == 'assistant'
    assert messages[2]['role'] == 'user'
    assert messages[3]['role'] == 'assistant'

    await client.delete(f'/api/sessions/{session_id}')


@pytest.mark.asyncio
async def test_session_deletion_cascades_to_messages(
    client: AsyncClient,
    mock_ollama: object,
    mock_anthropic: object,
) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    r = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': 'Test message'},
    )
    assert any(e['event'] == 'done' for e in parse_sse(r.text))

    await client.delete(f'/api/sessions/{session_id}')

    # Session no longer exists — its messages are gone with it (CASCADE)
    get = await client.get(f'/api/sessions/{session_id}')
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_session_with_source_ids_stores_selection(client: AsyncClient) -> None:
    from uuid import uuid4

    fake_source_id = str(uuid4())
    create = await client.post(
        '/api/sessions',
        json={'source_ids': [fake_source_id]},
    )
    assert create.status_code == 201
    data = create.json()
    assert fake_source_id in data['source_ids']

    await client.delete(f'/api/sessions/{data["id"]}')


@pytest.mark.asyncio
async def test_send_message_sse_error_event_on_stream_failure(
    client: AsyncClient,
    mock_ollama: object,
) -> None:
    from app.exceptions import ChatError

    async def _failing_stream(*args, **kwargs):
        yield 'Partial '
        raise ChatError('Anthropic API unexpectedly disconnected')

    from unittest.mock import patch

    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    with patch('app.services.chat.anthropic_client') as mock:
        mock.stream = _failing_stream
        response = await client.post(
            f'/api/sessions/{session_id}/messages',
            json={'content': 'Trigger a mid-stream failure'},
        )

    assert response.status_code == 200
    events = parse_sse(response.text)
    event_types = [e['event'] for e in events]
    assert 'error' in event_types
    assert 'done' not in event_types

    # Orphan user message must be cleaned up — no messages left in session
    session = await client.get(f'/api/sessions/{session_id}')
    assert session.json()['messages'] == []

    await client.delete(f'/api/sessions/{session_id}')


@pytest.mark.asyncio
async def test_send_message_title_not_overwritten_on_second_message(
    client: AsyncClient,
    mock_ollama: object,
    mock_anthropic: object,
) -> None:
    create = await client.post('/api/sessions', json={'source_ids': []})
    session_id = create.json()['id']

    first = 'What is Tailwind?'
    r1 = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': first},
    )
    assert any(e['event'] == 'done' for e in parse_sse(r1.text))

    r2 = await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': 'And how does it compare to Bootstrap?'},
    )
    assert any(e['event'] == 'done' for e in parse_sse(r2.text))

    session = await client.get(f'/api/sessions/{session_id}')
    # Title must remain from the FIRST message, not be overwritten by the second
    assert session.json()['title'] == first

    await client.delete(f'/api/sessions/{session_id}')
