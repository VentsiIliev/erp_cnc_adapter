import atexit
import asyncio
import logging
import os
import signal
import socket
import sys
import threading

from fastapi import Request

from src.core.config import Settings
from src.core.cnc_runtime import (
    cnc_server_path_from_dll,
    show_operator_ready_message,
    start_eding_gui_if_needed,
)
from src.core.cnc_server_process import start_cnc_server_if_needed
from src.cnc.cnc_client import CncClient
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.connection_manager import ConnectionManager
from src.cnc.mock_cnc_client import MockCncClient
from src.cnc.unavailable_cnc_client import UnavailableCncClient
from src.cnc.job_monitor import JobMonitor

logger = logging.getLogger(__name__)

PID_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "adapter.pid")
MANUAL_START_DEFER_GUI_FLAG = "manual_start_defer_gui.flag"


def _runtime_root() -> str:
    """Return the install/runtime directory used by operator launcher scripts."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _manual_start_defer_gui_flag_path() -> str:
    return os.path.join(_runtime_root(), MANUAL_START_DEFER_GUI_FLAG)


def _consume_manual_start_defer_gui_flag() -> bool:
    """Consume the one-shot START-CNC marker that defers GUI launch until ready."""
    flag_path = _manual_start_defer_gui_flag_path()
    if not os.path.exists(flag_path):
        return False
    try:
        os.remove(flag_path)
    except OSError as exc:
        logger.warning("Could not remove manual START-CNC GUI deferral flag: %s", exc)
    return True


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
        self._defer_gui_to_manual_launcher = _consume_manual_start_defer_gui_flag()
        if self._defer_gui_to_manual_launcher:
            logger.info("Manual START-CNC requested: deferring Eding GUI until adapter is CNC-ready")

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
        self.connection_manager = ConnectionManager(
            self.cnc_client,
            settings,
            on_ready=self._on_cnc_ready,
        )

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
        if self.settings.dev_mode or not self.settings.auto_start_cnc_server:
            return
        if self.settings.auto_start_eding_gui and not self._defer_gui_to_manual_launcher:
            logger.info("Skipping direct CncServer auto-start because Eding GUI auto-start is enabled")
            return

        cnc_server_exe = cnc_server_path_from_dll(self.settings.dll_path)

        if not os.path.isfile(cnc_server_exe):
            logger.warning("Auto-start: CncServer.exe not found at %s", cnc_server_exe)
            return

        result = start_cnc_server_if_needed(str(cnc_server_exe))
        if result.started:
            logger.info("Auto-started CncServer.exe from %s", cnc_server_exe)
        elif result.already_running:
            logger.info("Auto-start skipped because CncServer.exe is already running")
        else:
            logger.error("Auto-start CncServer.exe failed: %s", result.message)

    def _auto_start_eding_gui(self) -> bool:
        """Launch Eding GUI first when it should own the interactive CNC session."""
        if self.settings.dev_mode or not self.settings.auto_start_eding_gui:
            return False
        if self._defer_gui_to_manual_launcher:
            logger.info("Eding GUI auto-start deferred to START-CNC feedback launcher")
            return False
        return start_eding_gui_if_needed(self.settings.dll_path, self.settings.task_username)

    def _adapter_address(self) -> str:
        if self.settings.host and self.settings.host not in {"0.0.0.0", "::"}:
            host = self.settings.host
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("8.8.8.8", 80))
                host = sock.getsockname()[0]
            except OSError:
                host = "127.0.0.1"
            finally:
                sock.close()
        return f"{host}:{self.settings.port}"

    def _on_cnc_ready(self) -> None:
        """Run operator-facing startup actions after the adapter is truly CNC-ready."""
        if self.settings.auto_start_eding_gui:
            return

        if self.settings.show_operator_ready_message:
            show_operator_ready_message(
                self.settings.machine_number,
                self._adapter_address(),
                self.settings.task_username,
            )

    def start(self) -> None:
        gui_started = self._auto_start_eding_gui()
        if not gui_started:
            self._auto_start_cnc_server()
            self.connection_manager.start()
        else:
            asyncio.create_task(self._start_connection_manager_after_gui_delay())

        # Start job monitor to continuously watch for job starts/finishes.
        asyncio.create_task(self.job_monitor.start_monitoring())
        logger.info("Job monitor started - watching for job state changes")

    async def _start_connection_manager_after_gui_delay(self) -> None:
        delay = min(max(self.settings.cnc_retry_interval * 2, 10), 30)
        logger.info("Waiting %ds for Eding GUI/CncServer startup before connecting", delay)
        await asyncio.sleep(delay)
        self.connection_manager.start()

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

