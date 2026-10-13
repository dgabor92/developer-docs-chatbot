import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader

from app.api import health, sessions, sources
from app.clients.ollama import ollama_client
from app.config import settings
from app.db.connection import close_db_pool, init_db_pool
from app.db.migrate import run_migrations

_api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


async def _verify_api_key(key: str | None = Security(_api_key_header)) -> None:
    if settings.api_key and key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger = structlog.get_logger()
    await run_migrations()
    await init_db_pool()
    logger.info("startup_complete", environment=settings.environment)
    yield
    await close_db_pool()
    await ollama_client.aclose()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Developer Docs Chatbot",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Api-Key"],
    )

    _auth = [Depends(_verify_api_key)]
    app.include_router(health.router, prefix="/api")
    app.include_router(sources.router, prefix="/api", dependencies=_auth)
    app.include_router(sessions.router, prefix="/api", dependencies=_auth)

    return app


app = create_app()
