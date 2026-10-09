from fastapi import APIRouter
from pydantic import BaseModel

from app.clients.anthropic import anthropic_client
from app.clients.ollama import ollama_client
from app.db.connection import get_pool

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    database: str
    ollama: str
    anthropic: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_status = await _check_database()
    ollama_status = "ok" if await ollama_client.is_available() else "error"
    anthropic_status = "configured" if anthropic_client.is_configured() else "not_configured"

    critical_ok = db_status == "ok" and ollama_status == "ok"
    overall = "ok" if critical_ok else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        ollama=ollama_status,
        anthropic=anthropic_status,
    )


async def _check_database() -> str:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return "ok"
    except Exception:
        return "error"
