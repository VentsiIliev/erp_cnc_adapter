"""Live monitor page endpoint."""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    """Live monitoring page that auto-updates every second."""
    logger.info("GET /monitor - Live monitor page request")

    # Read the HTML file directly
    if getattr(sys, "frozen", False):
        template_path = Path(sys._MEIPASS) / "src" / "web" / "templates" / "monitor.html"
    else:
        template_path = Path(__file__).resolve().parent.parent / "web" / "templates" / "monitor.html"

    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Monitor page not found</h1>", status_code=404)

