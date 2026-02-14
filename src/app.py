import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.config import Settings
from src.app_state import AppState
from src.handlers import api_router
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services = AppState(settings)
        app.state.services = services
        services.start()
        yield
        await services.shutdown()

    app = FastAPI(title="ERP-CNC Adapter API", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def _unhandled_exception(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"status": 1, "message": f"Internal server error: {exc}"},
        )

    app.include_router(api_router)
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")

    # Favicon ──────────────────────────────────────────────────────────────
    _favicon = _resolve_favicon()

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        if _favicon and _favicon.exists():
            return FileResponse(_favicon, media_type="image/x-icon")
        return Response(status_code=204)

    return app


def _resolve_favicon() -> Path | None:
    """Locate resources/logo.ico relative to project root or frozen bundle."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    ico = base / "resources" / "logo.ico"
    return ico if ico.exists() else None
