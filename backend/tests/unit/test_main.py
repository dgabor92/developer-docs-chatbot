"""Tests for app/main.py — configure_logging, create_app, lifespan."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI


async def test_configure_logging_runs() -> None:
    import app.main as main_module  # importing covers `app = create_app()` (line 70)
    main_module.configure_logging()


async def test_create_app_returns_fastapi_with_routes() -> None:
    import app.main as main_module
    app = main_module.create_app()
    assert isinstance(app, FastAPI)
    # app has CORS middleware + the 3 API routers registered
    assert len(app.user_middleware) >= 1
    assert len(app.routes) > 3


async def test_lifespan_startup_and_shutdown() -> None:
    import app.main as main_module

    with (
        patch.object(main_module, 'run_migrations', AsyncMock()),
        patch.object(main_module, 'init_db_pool', AsyncMock()),
        patch.object(main_module, 'close_db_pool', AsyncMock()) as mock_close,
        patch.object(main_module, 'ollama_client') as mock_ollama,
    ):
        mock_ollama.aclose = AsyncMock()
        dummy = FastAPI()
        async with main_module.lifespan(dummy):
            main_module.run_migrations.assert_awaited_once()
            main_module.init_db_pool.assert_awaited_once()

        mock_close.assert_awaited_once()
        mock_ollama.aclose.assert_awaited_once()
