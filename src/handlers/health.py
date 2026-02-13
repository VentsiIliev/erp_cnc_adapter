import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.app_state import get_connection_manager
from src.services.connection_manager import ConnectionManager
from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_status_data(manager) -> dict:
    connected = manager.connected
    uptime = manager.uptime_seconds
    return {
        "status": "healthy" if connected else "degraded",
        "version": VERSION,
        "cnc": {
            "connected": connected,
            "state": manager.state,
            "retry_count": manager.retry_count,
            "last_error": manager.last_error,
            "uptime_seconds": round(uptime, 1) if uptime is not None else None,
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
        error_row = f"""
            <tr>
                <td class="label">Last error</td>
                <td class="value error">{cnc["last_error"]}</td>
            </tr>"""

    retry_row = ""
    if cnc["retry_count"] > 0:
        retry_row = f"""
            <tr>
                <td class="label">Retry count</td>
                <td class="value">{cnc["retry_count"]}</td>
            </tr>"""

    action_btn = ""
    if state == "cnc_not_running":
        action_btn = """
    <div style="padding:0 28px 16px;text-align:center">
      <form method="post" action="/api/cnc/start">
        <button type="submit" class="start-cnc-btn">&#9654; Start CNC</button>
      </form>
    </div>"""
    elif connected:
        action_btn = """
    <div style="padding:0 28px 16px;text-align:center">
      <form method="post" action="/api/cnc/stop">
        <button type="submit" class="stop-cnc-btn">&#9632; Stop CNC</button>
      </form>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>ERP-CNC Adapter</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.1), 0 4px 16px rgba(0,0,0,.06);
    width: 420px;
    max-width: 95vw;
    overflow: hidden;
  }}
  .header {{
    padding: 24px 28px 20px;
    border-bottom: 1px solid #e2e8f0;
  }}
  .header h1 {{
    font-size: 18px;
    font-weight: 600;
    color: #334155;
  }}
  .header .version {{
    font-size: 13px;
    color: #94a3b8;
    margin-top: 2px;
  }}
  .status-banner {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 18px 28px;
    background: {status_bg};
  }}
  .status-icon {{
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: {status_color};
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: bold;
    flex-shrink: 0;
  }}
  .status-text {{
    font-size: 16px;
    font-weight: 600;
    color: {status_color};
  }}
  .status-sub {{
    font-size: 13px;
    color: #64748b;
    margin-top: 1px;
  }}
  .details {{
    padding: 20px 28px 24px;
  }}
  .details table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .details td {{
    padding: 8px 0;
    font-size: 14px;
    vertical-align: top;
  }}
  .details tr + tr td {{
    border-top: 1px solid #f1f5f9;
  }}
  .label {{
    color: #64748b;
    width: 40%;
  }}
  .value {{
    font-weight: 500;
    text-align: right;
  }}
  .error {{
    color: #dc2626;
    font-weight: 400;
    font-size: 13px;
    word-break: break-word;
  }}
  .dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    position: relative;
    top: -1px;
  }}
  .dot-pulse {{
    background: #16a34a;
    animation: pulse 2s ease-in-out infinite;
  }}
  .dot-warn {{
    background: #dc2626;
    animation: pulse 1s ease-in-out infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: .4; }}
  }}
  .footer {{
    padding: 12px 28px;
    border-top: 1px solid #e2e8f0;
    text-align: center;
    font-size: 12px;
    color: #94a3b8;
  }}
  .footer a {{
    color: #64748b;
    text-decoration: none;
  }}
  .footer a:hover {{ text-decoration: underline; }}
  .docs-btn {{
    display: inline-block;
    margin-top: 8px;
    padding: 6px 18px;
    background: #3b82f6;
    color: #fff !important;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none !important;
    transition: background .15s;
  }}
  .docs-btn:hover {{ background: #2563eb; }}
  .start-cnc-btn {{
    display: inline-block;
    margin-top: 12px;
    padding: 10px 28px;
    background: #16a34a;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s;
  }}
  .start-cnc-btn:hover {{ background: #15803d; }}
  .stop-cnc-btn {{
    display: inline-block;
    margin-top: 12px;
    padding: 10px 28px;
    background: #dc2626;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s;
  }}
  .stop-cnc-btn:hover {{ background: #b91c1c; }}
  .update-link {{
    display: inline-block;
    margin-top: 8px;
    padding: 8px 20px;
    background: #f59e0b;
    color: #fff !important;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none !important;
    transition: background .15s;
  }}
  .update-link:hover {{ background: #d97706; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>ERP-CNC Adapter</h1>
      <div class="version">v{data["version"]}</div>
    </div>
    <div class="status-banner">
      <div class="status-icon">{status_icon}</div>
      <div>
        <div class="status-text">{status_label}</div>
        <div class="status-sub">CNC state: {cnc["state"]}</div>
      </div>
    </div>
    <div class="details">
      <table>
        <tr>
          <td class="label">Status</td>
          <td class="value"><span class="dot {dot_class}"></span>{data["status"].capitalize()}</td>
        </tr>
        <tr>
          <td class="label">Uptime</td>
          <td class="value">{_format_uptime(cnc["uptime_seconds"])}</td>
        </tr>{retry_row}{error_row}
      </table>
    </div>{action_btn}
    <div class="footer">
      Auto-refreshes every 5 s &middot; <a href="/api/health">JSON API</a>
      <br><a class="docs-btn" href="/docs">API Docs</a>
      <br><a class="update-link" href="/update">&#8635; Update Adapter</a>
    </div>
  </div>
</body>
</html>"""


@router.get("/")
async def home(
    request: Request,
    manager: ConnectionManager = Depends(get_connection_manager),
):
    data = _build_status_data(manager)
    status_code = 200 if data["cnc"]["connected"] else 503

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(content=_render_html(data), status_code=status_code)

    return JSONResponse(content=data, status_code=status_code)


@router.get("/api/health")
async def health_json(
    manager: ConnectionManager = Depends(get_connection_manager),
):
    data = _build_status_data(manager)
    status_code = 200 if data["cnc"]["connected"] else 503
    return JSONResponse(content=data, status_code=status_code)


