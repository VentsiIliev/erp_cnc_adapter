"""Configuration page endpoint."""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
async def config_page():
    """Configuration management page."""
    logger.info("GET /config - Configuration page request")

    # Read the HTML file directly
    if getattr(sys, "frozen", False):
        template_path = Path(sys._MEIPASS) / "src" / "web" / "templates" / "config.html"
    else:
        template_path = Path(__file__).resolve().parent.parent / "web" / "templates" / "config.html"

    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Configuration page not found</h1>", status_code=404)

