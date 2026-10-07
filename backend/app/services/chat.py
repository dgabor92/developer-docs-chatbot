from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import structlog

from app.clients.anthropic import anthropic_client
from app.db.sessions import (
    create_message,
    delete_message,
    get_session,
    list_messages,
    update_session_title,
)
from app.exceptions import NotFoundError
from app.services.retrieval import ChunkResult, retrieval_service

logger = structlog.get_logger()

MAX_HISTORY_MESSAGES = 10

SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful assistant that answers questions about developer documentation.

Use the following documentation excerpts to answer the user's question.
If the context does not contain enough information to answer confidently, say so clearly.
Always cite the source URLs when referencing specific information.

Context:
{context}"""


def _build_context(chunks: list[ChunkResult]) -> str:
    if not chunks:
        return 'No relevant documentation found.'
    parts = []
    for i, chunk in enumerate(chunks, 1):
        label = chunk.title or chunk.url
        parts.append(f'[{i}] {label}\nURL: {chunk.url}\n\n{chunk.content}')
    return '\n\n---\n\n'.join(parts)


def _truncate_history(
    messages: list[dict[str, Any]],
    max_messages: int = MAX_HISTORY_MESSAGES,
) -> list[dict[str, str]]:
    recent = messages[-max_messages:] if len(messages) > max_messages else messages
    # Claude requires the first message to be from the user
    while recent and recent[0]['role'] != 'user':
        recent = recent[1:]
    return [{'role': msg['role'], 'content': msg['content']} for msg in recent]


class ChatService:
    async def send_message(
        self,
        session_id: UUID,
        content: str,
    ) -> dict[str, Any]:
        session = await get_session(session_id)
        if session is None:
            raise NotFoundError('session', str(session_id))

        await create_message(session_id, 'user', content)

        source_ids = list(session['source_ids'] or [])
        chunks = await retrieval_service.search(content, source_ids)

        history = await list_messages(session_id)
        messages = _truncate_history(history)

        system = SYSTEM_PROMPT_TEMPLATE.format(context=_build_context(chunks))
        response_text = await anthropic_client.complete(system, messages)

        sources = [
            {'url': c.url, 'title': c.title, 'score': c.score}
            for c in chunks
        ]
        message = await create_message(session_id, 'assistant', response_text, sources)

        if session['title'] is None:
            await update_session_title(session_id, content[:80])

        logger.info(
            'chat_message_sent',
            session_id=str(session_id),
            chunks_used=len(chunks),
        )

        return dict(message) | {'sources': sources}

    async def stream_message(
        self,
        session_id: UUID,
        content: str,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        session = await get_session(session_id)
        if session is None:
            raise NotFoundError('session', str(session_id))

        source_ids = list(session['source_ids'] or [])

        user_msg = await create_message(session_id, 'user', content)

        chunks = await retrieval_service.search(content, source_ids)
        history = await list_messages(session_id)
        messages = _truncate_history(history)

        system = SYSTEM_PROMPT_TEMPLATE.format(context=_build_context(chunks))

        full_text = ''
        try:
            async for token in anthropic_client.stream(system, messages):
                full_text += token
                yield 'token', {'content': token}
        except Exception:
            # Streaming failed — remove the orphan user message to keep history consistent
            await delete_message(user_msg['id'])
            raise

        sources = [
            {'url': c.url, 'title': c.title, 'score': c.score}
            for c in chunks
        ]
        yield 'sources', {'sources': sources}

        message = await create_message(session_id, 'assistant', full_text, sources)

        if session['title'] is None:
            await update_session_title(session_id, content[:80])

        logger.info(
            'chat_message_streamed',
            session_id=str(session_id),
            chunks_used=len(chunks),
            tokens=len(full_text),
        )

        yield 'done', {
            'message_id': str(message['id']),
            'session_id': str(session_id),
        }


chat_service = ChatService()
