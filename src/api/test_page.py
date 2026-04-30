"""Test page for manual job monitoring testing."""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.api.dashboard_page import dashboard_response

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/test", response_class=HTMLResponse)
async def test_page():
    """Render the unified dashboard focused on testing."""
    logger.info("GET /test - Unified dashboard testing view request")
    return dashboard_response("testing")

