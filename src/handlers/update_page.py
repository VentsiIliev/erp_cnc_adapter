"""
Update Page Handler - Dedicated page for adapter updates
"""
import logging
from pathlib import Path
from string import Template

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

_TEMPLATE = Template(
    (Path(__file__).resolve().parent.parent / "templates" / "update.html").read_text()
)


def _render_update_page() -> str:
    return _TEMPLATE.substitute(version=VERSION)


@router.get("/update")
async def update_page(request: Request):
    """Render the dedicated update page."""
    return HTMLResponse(content=_render_update_page())
