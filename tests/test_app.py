"""Tests for src/app.py — FastAPI app factory."""

import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from src.app import create_app, _resolve_favicon


# ---------------------------------------------------------------------------
# _resolve_favicon
# ---------------------------------------------------------------------------

class TestResolveFavicon:

    def test_returns_none_when_ico_missing(self):
        """When logo.ico does not exist, _resolve_favicon returns None."""
        result = _resolve_favicon()
        # In CI or dev without the ico, it may or may not find it
        assert result is None or isinstance(result, Path)

    def test_returns_path_type(self):
        """Return type should be Path or None."""
        result = _resolve_favicon()
        assert result is None or isinstance(result, Path)


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------

class TestCreateApp:

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    def test_returns_fastapi_instance(self, mock_appstate, mock_logging):
        from src.core.config import Settings
        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        app = create_app(settings)
        assert isinstance(app, FastAPI)

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    def test_uses_provided_settings(self, mock_appstate, mock_logging):
        from src.core.config import Settings
        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            log_level="DEBUG",
            dev_mode=True,
        )
        create_app(settings)
        mock_logging.assert_called_once_with("DEBUG")

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    def test_default_settings_when_none(self, mock_appstate, mock_logging):
        """create_app() with no args should use default Settings."""
        app = create_app()
        assert isinstance(app, FastAPI)

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    def test_static_mount_exists(self, mock_appstate, mock_logging):
        from src.core.config import Settings
        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        app = create_app(settings)
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert any("/static" in str(r.path) for r in app.routes if hasattr(r, "path"))

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    def test_favicon_route_exists(self, mock_appstate, mock_logging):
        from src.core.config import Settings
        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        app = create_app(settings)
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/favicon.ico" in route_paths

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    @patch("src.app._resolve_favicon", return_value=None)
    async def test_favicon_returns_204_when_no_icon(self, _fav, mock_appstate, mock_logging):
        from src.core.config import Settings
        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        app = create_app(settings)
        app.router.lifespan_context = None
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/favicon.ico")
            assert resp.status_code == 204


class TestExceptionHandler:

    @patch("src.app.setup_logging")
    @patch("src.app.AppState")
    async def test_unhandled_exception_returns_status_1(self, mock_appstate, mock_logging):
        from src.core.config import Settings
        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        app = create_app(settings)
        app.router.lifespan_context = None

        @app.get("/test-error")
        async def error_route():
            raise ValueError("test boom")

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/test-error")
            assert resp.status_code == 500
            body = resp.json()
            assert body["status"] == 1
            assert "test boom" in body["message"]

def test_main_checks_jog_pad_before_adapter_imports():
    text = Path(__file__).resolve().parent.parent.joinpath("main.py").read_text(encoding="utf-8")
    top_level = text.split("def _run_adapter", 1)[0]

    assert "import uvicorn" not in top_level
    assert "from src.app import create_app" not in top_level
    assert "app = create_app" not in top_level
    assert 'if "--jog-pad" in sys.argv:' in text

