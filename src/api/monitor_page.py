"""Live monitor page endpoint."""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.api.dashboard_page import render_dashboard

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    """Render the unified dashboard focused on live monitoring."""
    logger.info("GET /monitor - Unified dashboard monitor view request")
    return HTMLResponse(content=render_dashboard("monitor"))

