import asyncio
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from src.core.cnc_server_process import start_cnc_server_if_needed
from src.core.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/cnc/start")
async def start_cnc(request: Request):
    """
    Start the CNC Server (CncServer.exe).

    This starts only the server process, not the GUI.
    The adapter connects to CncServer to control the CNC machine.
    """
    settings = Settings()
    cnc_dir = os.path.dirname(settings.dll_path)
    cnc_server_exe = os.path.join(cnc_dir, "CncServer.exe")

    if not os.path.isfile(cnc_server_exe):
        logger.error("CNC Server executable not found: %s", cnc_server_exe)
        return JSONResponse(
            content={"error": f"CncServer.exe not found at {cnc_server_exe}"},
            status_code=404,
        )

    result = start_cnc_server_if_needed(cnc_server_exe)
    if result.already_running:
        manager = request.app.state.services.connection_manager
        manager.nudge()
        return RedirectResponse(url="/", status_code=303)

    if not result.started:
        return JSONResponse(content={"error": result.message}, status_code=500)

    # Give server a moment to initialize (non-blocking)
    await asyncio.sleep(1)

    if result.pid is not None:
        logger.info("CNC Server start request completed for PID: %d", result.pid)

    # Wake up the ConnectionManager so it retries immediately
    manager = request.app.state.services.connection_manager
    manager.nudge()
    return RedirectResponse(url="/", status_code=303)
