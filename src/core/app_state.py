import atexit
import logging
import os
import signal
import threading

from fastapi import Request

from src.core.config import Settings
from src.core.cnc_server_process import start_cnc_server_if_needed
from src.cnc.cnc_client import CncClient
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.connection_manager import ConnectionManager
from src.cnc.mock_cnc_client import MockCncClient
from src.cnc.unavailable_cnc_client import UnavailableCncClient
from src.cnc.job_monitor import JobMonitor

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
            try:
                self.cnc_client = CncClient(settings)
            except Exception as exc:
                logger.error("CNC client initialization failed, starting in degraded mode: %s", exc)
                self.cnc_client = UnavailableCncClient(str(exc))
        self.connection_manager = ConnectionManager(self.cnc_client, settings)

        # Initialize job monitor (runs continuously to detect job starts/finishes)
        self.job_monitor = JobMonitor(
            self.cnc_client,
            poll_interval=settings.job_monitor_poll_interval,
            report_url=settings.job_done_report_url
        )
        logger.info("CNC client initialized (connection managed by ConnectionManager)")
        logger.info("Job monitor initialized (will start with application)")

        # Safety net: disconnect even on unhandled crashes
        atexit.register(self.cnc_client.disconnect)

    def _auto_start_cnc_server(self) -> None:
        """Launch CncServer.exe on startup if it exists and isn't already running."""
        if self.settings.dev_mode:
            return

        cnc_dir = os.path.dirname(self.settings.dll_path)
        cnc_server_exe = os.path.join(cnc_dir, "CncServer.exe")

        if not os.path.isfile(cnc_server_exe):
            logger.warning("Auto-start: CncServer.exe not found at %s", cnc_server_exe)
            return

        result = start_cnc_server_if_needed(cnc_server_exe)
        if result.started:
            logger.info("Auto-started CncServer.exe from %s", cnc_server_exe)
        elif result.already_running:
            logger.info("Auto-start skipped because CncServer.exe is already running")
        else:
            logger.error("Auto-start CncServer.exe failed: %s", result.message)

    def start(self) -> None:
        self._auto_start_cnc_server()
        self.connection_manager.start()
        # Start job monitor to continuously watch for job state changes
        import asyncio
        asyncio.create_task(self.job_monitor.start_monitoring())
        logger.info("Job monitor started - watching for job state changes")

    async def shutdown(self) -> None:
        # Watchdog: force-exit if DLL threads keep the process alive
        watchdog = threading.Timer(5.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()

        # Stop job monitor if one exists
        if self.job_monitor is not None and self.job_monitor.is_monitoring:
            logger.info("Stopping job monitor...")
            await self.job_monitor.stop_monitoring()

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

