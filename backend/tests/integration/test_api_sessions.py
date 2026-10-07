"""Integration tests for the sessions API — require Docker PostgreSQL to be running."""
import pytest
from httpx import AsyncClient

MOCK_RESPONSE = 'This is a helpful answer about the documentation.'


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
    data = response.json()
    assert data['role'] == 'assistant'
    assert data['content'] == MOCK_RESPONSE
    assert data['session_id'] == session_id

    session = await client.get(f'/api/sessions/{session_id}')
    messages = session.json()['messages']
    assert len(messages) == 2
    assert messages[0]['role'] == 'user'
    assert messages[1]['role'] == 'assistant'

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
    await client.post(
        f'/api/sessions/{session_id}/messages',
        json={'content': question},
    )

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
