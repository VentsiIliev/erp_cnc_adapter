import atexit
import logging
import os
import signal
import threading

from fastapi import Request

from src.core.config import Settings
from src.cnc.cnc_client import CncClient
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.connection_manager import ConnectionManager
from src.cnc.mock_cnc_client import MockCncClient

logger = logging.getLogger(__name__)

PID_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "adapter.pid")


def _kill_stale_adapter() -> None:
    """If a previous adapter process is still running, kill it."""
    try:
        with open(PID_FILE) as f:
            old_pid = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return

    if old_pid == os.getpid():
        return

    try:
        os.kill(old_pid, signal.SIGTERM)
        logger.warning("Killed stale adapter process (PID %d)", old_pid)
    except OSError:
        pass  # already dead


def _write_pid_file() -> None:
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


class AppState:
    """Application-wide service container stored on ``app.state.services``."""

    def __init__(self, settings: Settings) -> None:
        _kill_stale_adapter()
        _write_pid_file()

        self.settings = settings

        logger.info("Initializing CNC client...")
        if settings.dev_mode:
            logger.warning("DEV_MODE enabled — using mock CNC client")
            self.cnc_client: CncClientProtocol = MockCncClient()
        else:
            self.cnc_client: CncClientProtocol = CncClient(settings)
        self.connection_manager = ConnectionManager(self.cnc_client, settings)
        logger.info("CNC client initialized (connection managed by ConnectionManager)")

        # Safety net: disconnect even on unhandled crashes
        atexit.register(self.cnc_client.disconnect)

    def start(self) -> None:
        self.connection_manager.start()

    async def shutdown(self) -> None:
        # Watchdog: force-exit if DLL threads keep the process alive
        watchdog = threading.Timer(5.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()

        logger.info("Disconnecting CNC client...")
        self.cnc_client.disconnect()
        logger.info("Stopping ConnectionManager...")
        await self.connection_manager.stop()
        self._remove_pid_file()
        logger.info("Shutdown complete")

        watchdog.cancel()

    @staticmethod
    def _remove_pid_file() -> None:
        try:
            os.remove(PID_FILE)
        except OSError:
            pass


# --- FastAPI Depends() getters ---------------------------------------------------

def get_cnc_client(request: Request) -> CncClientProtocol:
    return request.app.state.services.cnc_client


def get_connection_manager(request: Request) -> ConnectionManager:
    return request.app.state.services.connection_manager


def get_settings(request: Request) -> Settings:
    return request.app.state.services.settings

