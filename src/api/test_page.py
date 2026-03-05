"""Test page for manual job monitoring testing."""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/test", response_class=HTMLResponse)
async def test_page():
    """Test page for job monitoring."""
    logger.info("GET /test - Test page request")

    # Read the HTML file directly
    if getattr(sys, "frozen", False):
        template_path = Path(sys._MEIPASS) / "src" / "web" / "templates" / "test.html"
    else:
        template_path = Path(__file__).resolve().parent.parent / "web" / "templates" / "test.html"

    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Test page not found</h1>", status_code=404)

