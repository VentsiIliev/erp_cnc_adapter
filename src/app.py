import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    app.include_router(api_router)
    return app
