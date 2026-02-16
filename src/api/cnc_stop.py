import ctypes
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/cnc/stop")
async def stop_cnc(request: Request):
    """Disconnect the adapter, then shut down CNC and CncServer."""
    # Disconnect adapter first so it doesn't hold the DLL connection
    client = request.app.state.services.cnc_client
    client.disconnect()
    client._connected = False  # noqa: SLF001

    logger.info("Stopping CNC processes...")
    # Use taskkill to cleanly stop both processes
    for proc in ("cnc.exe", "CncServer.exe"):
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "taskkill", f"/IM {proc}", None, 0,
        )
        if ret > 32:
            logger.info("Sent stop signal to %s", proc)
        else:
            logger.warning("Failed to stop %s (code %d)", proc, ret)

    return RedirectResponse(url="/", status_code=303)
