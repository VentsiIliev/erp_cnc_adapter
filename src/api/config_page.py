"""Configuration page endpoint."""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.api.dashboard_page import render_dashboard

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
async def config_page():
    """Render the unified dashboard focused on configuration."""
    logger.info("GET /config - Unified dashboard config view request")
    return HTMLResponse(content=render_dashboard("config"))

