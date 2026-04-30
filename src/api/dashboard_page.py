"""Unified dashboard page endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

if getattr(sys, "frozen", False):
    _SRC_DIR = Path(sys._MEIPASS) / "src"
else:
    _SRC_DIR = Path(__file__).resolve().parent.parent


def render_dashboard(initial_view: str = "overview") -> str:
    template_path = _SRC_DIR / "web" / "templates" / "dashboard.html"
    html = template_path.read_text(encoding="utf-8")
    return html.replace("__VERSION__", VERSION).replace("__INITIAL_VIEW__", initial_view)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Unified dashboard for health, monitor, config, test and update tools."""
    logger.info("GET /dashboard - Unified dashboard request")

    try:
        return HTMLResponse(content=render_dashboard("overview"))
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard page not found</h1>", status_code=404)
