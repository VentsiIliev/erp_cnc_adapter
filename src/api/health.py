import logging
import sys
from pathlib import Path
from string import Template

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.core.app_state import get_connection_manager
from src.cnc.connection_manager import ConnectionManager
from src.api.dashboard_page import dashboard_response
from src.api.job_status import STATE_MAP
from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

if getattr(sys, "frozen", False):
    _SRC_DIR = Path(sys._MEIPASS) / "src"
else:
    _SRC_DIR = Path(__file__).resolve().parent.parent

_TEMPLATE = Template((_SRC_DIR / "web" / "templates" / "health.html").read_text())


def _build_status_data(manager) -> dict:
    connected = manager.connected
    uptime = manager.uptime_seconds
    return {
        "status": "healthy" if connected else "degraded",
        "version": VERSION,
        "cnc": {
            "connected": connected,
            "state": manager.state,
            "machine_state": manager.machine_state,
            "machine_state_text": STATE_MAP.get(manager.machine_state, None),
            "retry_count": manager.retry_count,
            "last_error": manager.last_error,
            "uptime_seconds": round(uptime, 1) if uptime is not None else None,
        },
    }


def _build_indicator_status_data(manager) -> dict:
    cnc = _build_status_data(manager)["cnc"]
    connected = bool(cnc["connected"])
    machine_state = cnc["machine_state"]
    last_error = cnc["last_error"]

    if connected and machine_state in (1, 2):
        interpreter_status = "ready"
    elif connected:
        interpreter_status = "not_ready"
    elif last_error:
        interpreter_status = "error"
    else:
        interpreter_status = "offline"

    return {
        "status": "ok",
        "version": VERSION,
        "adapter": {
            "online": True,
            "status": "running",
        },
        "interpreter": {
            "online": connected,
            "status": interpreter_status,
            "machine_state": machine_state,
            "machine_state_text": cnc["machine_state_text"],
            "connection_state": cnc["state"],
            "last_error": last_error,
        },
    }


def _format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "&mdash;"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h}h {m}m"


def _render_html(data: dict) -> str:
    cnc = data["cnc"]
    connected = cnc["connected"]

    state = cnc["state"]
    if connected:
        status_color = "#16a34a"
        status_bg = "#dcfce7"
        status_label = "Connected"
        status_icon = "&#10003;"
        dot_class = "dot-pulse"
    elif state == "cnc_not_running":
        status_color = "#9333ea"
        status_bg = "#f3e8ff"
        status_label = "CNC Not Running"
        status_icon = "&#9724;"
        dot_class = "dot-warn"
    else:
        status_color = "#dc2626"
        status_bg = "#fee2e2"
        status_label = "Disconnected"
        status_icon = "&#10007;"
        dot_class = "dot-warn"

    error_row = ""
    if cnc["last_error"]:
        error_row = (
            '\n            <tr>'
            '\n                <td class="label">Last error</td>'
            f'\n                <td class="value error">{cnc["last_error"]}</td>'
            "\n            </tr>"
        )

    retry_row = ""
    if cnc["retry_count"] > 0:
        retry_row = (
            '\n            <tr>'
            '\n                <td class="label">Retry count</td>'
            f'\n                <td class="value">{cnc["retry_count"]}</td>'
            "\n            </tr>"
        )

    action_btn = ""
    if state == "cnc_not_running":
        action_btn = (
            '\n    <div style="padding:0 28px 16px;text-align:center">'
            '\n      <a href="/api/cnc/start" class="start-cnc-btn" style="display:inline-block;text-decoration:none">&#9654; Start CNC</a>'
            "\n    </div>"
        )
    elif connected:
        action_btn = (
            '\n    <div style="padding:0 28px 16px;text-align:center">'
            '\n      <a href="/api/cnc/stop" class="stop-cnc-btn" style="display:inline-block;text-decoration:none">&#9632; Stop CNC</a>'
            "\n    </div>"
        )

    return _TEMPLATE.substitute(
        version=data["version"],
        status_bg=status_bg,
        status_color=status_color,
        status_icon=status_icon,
        status_label=status_label,
        dot_class=dot_class,
        status_text=data["status"].capitalize(),
        uptime=_format_uptime(cnc["uptime_seconds"]),
        cnc_state=cnc["state"],
        retry_row=retry_row,
        error_row=error_row,
        action_btn=action_btn,
    )


@router.get("/")
async def home(
    request: Request,
    manager: ConnectionManager = Depends(get_connection_manager),
):
    data = _build_status_data(manager)
    status_code = 200 if data["cnc"]["connected"] else 503

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return dashboard_response("overview", status_code=200)

    return JSONResponse(content=data, status_code=status_code)


@router.get("/api/status/indicator")
async def indicator_status_json(
    manager: ConnectionManager = Depends(get_connection_manager),
):
    return JSONResponse(content=_build_indicator_status_data(manager), status_code=200)


@router.get("/api/health")
async def health_json(
    manager: ConnectionManager = Depends(get_connection_manager),
):
    data = _build_status_data(manager)
    status_code = 200 if data["cnc"]["connected"] else 503
    return JSONResponse(content=data, status_code=status_code)
