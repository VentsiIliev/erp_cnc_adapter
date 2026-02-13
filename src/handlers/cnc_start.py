import asyncio
import logging
import os
import subprocess

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from src.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/cnc/start")
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

    logger.info("Starting CNC Server: %s", cnc_server_exe)

    try:
        # Start CncServer.exe as a detached background process.
        # Use DEVNULL so pipes don't block the child if it writes output.
        process = subprocess.Popen(
            [cnc_server_exe],
            cwd=cnc_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        logger.info("CNC Server started with PID: %d", process.pid)

        # Give server a moment to initialize (non-blocking)
        await asyncio.sleep(1)

        # Verify it's still running
        if process.poll() is None:
            # Wake up the ConnectionManager so it retries immediately
            manager = request.app.state.services.connection_manager
            manager.nudge()

            return RedirectResponse(url="/", status_code=303)
        else:
            logger.error("CNC Server exited immediately with code: %d", process.returncode)
            return JSONResponse(
                content={"error": f"CNC Server exited immediately (code {process.returncode})"},
                status_code=500,
            )

    except Exception as e:
        logger.error("Failed to start CNC Server: %s", str(e), exc_info=True)
        return JSONResponse(
            content={"error": f"Failed to start CNC Server: {str(e)}"},
            status_code=500,
        )
