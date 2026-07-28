import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.core.config import Settings
from src.core.app_state import AppState
from src.api import api_router
from src.core.http_logging import log_http_request_response
from src.core.logging_config import setup_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    create_start = time.perf_counter()
    setup_logging(settings.log_level)
    logger.info("Startup timing: logging configured for create_app")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        lifespan_start = time.perf_counter()
        logger.info("Startup timing: FastAPI lifespan starting")
        state_start = time.perf_counter()
        services = AppState(settings)
        logger.info("Startup timing: AppState initialized in %.1fms", (time.perf_counter() - state_start) * 1000)
        app.state.services = services
        services_start = time.perf_counter()
        services.start()
        logger.info("Startup timing: AppState.start returned in %.1fms", (time.perf_counter() - services_start) * 1000)
        logger.info("Startup timing: FastAPI lifespan startup completed in %.1fms", (time.perf_counter() - lifespan_start) * 1000)
        yield
        shutdown_start = time.perf_counter()
        logger.info("Shutdown timing: FastAPI lifespan shutdown starting")
        await services.shutdown()
        logger.info("Shutdown timing: FastAPI lifespan shutdown completed in %.1fms", (time.perf_counter() - shutdown_start) * 1000)

    app = FastAPI(title="ERP-CNC Adapter API", lifespan=lifespan)
    app.middleware("http")(log_http_request_response)

    @app.exception_handler(Exception)
    async def _unhandled_exception(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"status": 1, "message": f"Internal server error: {exc}"},
        )

    app.include_router(api_router)

    if getattr(sys, "frozen", False):
        _static_dir = Path(sys._MEIPASS) / "src" / "web" / "static"
    else:
        _static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    _favicon = _resolve_favicon()

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        if _favicon and _favicon.exists():
            return FileResponse(_favicon, media_type="image/x-icon")
        return Response(status_code=204)

    logger.info("Startup timing: create_app completed in %.1fms", (time.perf_counter() - create_start) * 1000)
    return app


def _resolve_favicon() -> Path | None:
    """Locate resources/logo.ico relative to project root or frozen bundle."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    ico = base / "resources" / "logo.ico"
    return ico if ico.exists() else None
