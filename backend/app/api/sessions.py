import json
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, status

from app.db.sessions import (
    create_session,
    delete_session,
    get_session,
    list_messages,
    list_sessions,
)
from app.exceptions import ChatError, NotFoundError, RetrievalError
from app.models.session import (
    MessageCreate,
    MessageResponse,
    SessionCreate,
    SessionResponse,
    SessionWithMessages,
    SourceCitation,
)
from app.services.chat import chat_service

logger = structlog.get_logger()
router = APIRouter(prefix='/sessions', tags=['sessions'])


def _message_from_row(row: dict) -> MessageResponse:  # type: ignore[type-arg]
    sources = None
    raw = row.get('sources')
    if raw is not None:
        # asyncpg returns JSONB as a JSON string — decode if needed
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        sources = [SourceCitation(**s) for s in parsed]
    return MessageResponse(
        id=row['id'],
        session_id=row['session_id'],
        role=row['role'],
        content=row['content'],
        sources=sources,
        created_at=row['created_at'],
    )


@router.post('', response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_session(body: SessionCreate) -> SessionResponse:
    row = await create_session(body.source_ids)
    return SessionResponse(**row)


@router.get('', response_model=list[SessionResponse])
async def list_all_sessions() -> list[SessionResponse]:
    rows = await list_sessions()
    return [SessionResponse(**r) for r in rows]


@router.get('/{session_id}', response_model=SessionWithMessages)
async def get_session_with_messages(session_id: UUID) -> SessionWithMessages:
    row = await get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail='Session not found')
    messages = await list_messages(session_id)
    return SessionWithMessages(
        **row,
        messages=[_message_from_row(m) for m in messages],
    )


@router.delete('/{session_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(session_id: UUID) -> None:
    deleted = await delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='Session not found')


@router.post('/{session_id}/messages', response_model=MessageResponse)
async def send_message(session_id: UUID, body: MessageCreate) -> MessageResponse:
    try:
        row = await chat_service.send_message(session_id, body.content)
    except NotFoundError:
        raise HTTPException(status_code=404, detail='Session not found')
    except (ChatError, RetrievalError) as e:
        logger.error('chat_error', session_id=str(session_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    return _message_from_row(row)
