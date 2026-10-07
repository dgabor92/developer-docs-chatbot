import pytest

from app.services.chat import MAX_HISTORY_MESSAGES, _build_context, _truncate_history
from app.services.retrieval import ChunkResult


def _make_chunks(n: int) -> list[ChunkResult]:
    return [
        ChunkResult(
            url=f'https://example.com/docs/page{i}',
            title=f'Page {i}',
            content=f'Content for page {i}.',
            score=0.9 - i * 0.05,
        )
        for i in range(1, n + 1)
    ]


def _make_history(roles: list[str]) -> list[dict[str, str]]:
    return [{'role': role, 'content': f'Message {i}'} for i, role in enumerate(roles)]


def test_build_context_empty_chunks() -> None:
    context = _build_context([])
    assert 'No relevant documentation' in context


def test_build_context_formats_chunks() -> None:
    chunks = _make_chunks(2)
    context = _build_context(chunks)

    assert 'Page 1' in context
    assert 'https://example.com/docs/page1' in context
    assert 'Content for page 1.' in context
    assert '[1]' in context
    assert '[2]' in context
    assert '---' in context


def test_build_context_uses_url_as_fallback_title() -> None:
    chunk = ChunkResult(url='https://example.com/no-title', title=None, content='text', score=0.5)
    context = _build_context([chunk])
    assert 'https://example.com/no-title' in context


def test_truncate_history_under_limit() -> None:
    history = _make_history(['user', 'assistant', 'user'])
    result = _truncate_history(history, max_messages=10)
    assert len(result) == 3
    assert all(k in result[0] for k in ('role', 'content'))


def test_truncate_history_over_limit() -> None:
    roles = ['user', 'assistant'] * 10  # 20 messages
    history = _make_history(roles)
    result = _truncate_history(history, max_messages=MAX_HISTORY_MESSAGES)
    assert len(result) == MAX_HISTORY_MESSAGES


def test_truncate_history_always_starts_with_user() -> None:
    # 11 messages: user, asst, user, asst, ..., user, asst, user
    # Truncating to 10 drops the first user, leaving asst as first
    # The function should then also drop that leading assistant message
    roles = ['user', 'assistant'] * 5 + ['user']  # 11 total
    history = _make_history(roles)
    result = _truncate_history(history, max_messages=10)
    assert result[0]['role'] == 'user'


def test_truncate_history_strips_assistant_prefix() -> None:
    history = _make_history(['assistant', 'user', 'assistant'])
    result = _truncate_history(history, max_messages=10)
    assert result[0]['role'] == 'user'
    assert len(result) == 2


def test_truncate_history_returns_only_role_and_content() -> None:
    history = [
        {'role': 'user', 'content': 'Hello', 'id': 'abc', 'sources': None}
    ]
    result = _truncate_history(history)
    assert set(result[0].keys()) == {'role', 'content'}
