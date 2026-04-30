"""
Update Page Handler - Dedicated page for adapter updates
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.api.dashboard_page import render_dashboard

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/update")
async def update_page(request: Request):
    """Render the unified dashboard focused on maintenance."""
    return HTMLResponse(content=render_dashboard("maintenance"))
