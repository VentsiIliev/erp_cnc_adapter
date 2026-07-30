import atexit
import asyncio
import logging
import os
import signal
import socket
import sys
import threading
import time

from fastapi import Request

from src.core.config import Settings
from src.core.cnc_runtime import (
    cnc_server_path_from_dll,
    start_eding_gui_if_needed,
)
from src.core.cnc_server_process import start_cnc_server_if_needed
from src.core.task_config import request_adapter_recovery_restart
from src.cnc.cnc_client import CncClient
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.connection_manager import ConnectionManager
from src.cnc.mock_cnc_client import MockCncClient
from src.cnc.unavailable_cnc_client import UnavailableCncClient
from src.cnc.job_monitor import JobMonitor
from src.cnc.message_monitor import CncMessageService
from src.cnc.physical_button_monitor import PhysicalButtonService

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
        init_start = time.perf_counter()
        logger.info(
            "Startup timing: AppState init begin pid=%s runtime_root=%s",
            os.getpid(),
            _runtime_root(),
        )

        pid_start = time.perf_counter()
        _kill_stale_adapter()
        _write_pid_file()
        logger.info("Startup timing: PID file handling completed in %.1fms", (time.perf_counter() - pid_start) * 1000)

        self.settings = settings
        self._defer_gui_to_manual_launcher = _consume_manual_start_defer_gui_flag()
        logger.info(
            "Startup configuration: dev_mode=%s auto_start_cnc_server=%s auto_start_eding_gui=%s "
            "port=%s dll_path=%s ini_path=%s task_username=%s defer_gui=%s",
            settings.dev_mode,
            settings.auto_start_cnc_server,
            settings.auto_start_eding_gui,
            settings.port,
            settings.dll_path,
            settings.ini_path,
            settings.task_username or "<system/default>",
            self._defer_gui_to_manual_launcher,
        )
        if self._defer_gui_to_manual_launcher:
            logger.info("Manual START-CNC requested: deferring Eding GUI until adapter is CNC-ready")

        cnc_client_start = time.perf_counter()
        logger.info("Initializing CNC client...")
        if settings.dev_mode:
            logger.warning("DEV_MODE enabled - using mock CNC client")
            self.cnc_client: CncClientProtocol = MockCncClient()
        else:
            try:
                self.cnc_client = CncClient(settings)
            except Exception as exc:
                logger.error("CNC client initialization failed, starting in degraded mode: %s", exc)
                self.cnc_client = UnavailableCncClient(str(exc))
        logger.info(
            "Startup timing: CNC client object ready in %.1fms type=%s",
            (time.perf_counter() - cnc_client_start) * 1000,
            type(self.cnc_client).__name__,
        )

        connection_manager_start = time.perf_counter()
        self.connection_manager = ConnectionManager(
            self.cnc_client,
            settings,
            on_ready=self._on_cnc_ready,
            on_cnc_server_missing=self._restart_adapter_after_cnc_server_loss,
        )
        logger.info(
            "Startup timing: ConnectionManager created in %.1fms",
            (time.perf_counter() - connection_manager_start) * 1000,
        )

        job_monitor_start = time.perf_counter()
        self.job_monitor = JobMonitor(
            self.cnc_client,
            poll_interval=settings.job_monitor_poll_interval,
            report_url=settings.job_done_report_url,
        )
        logger.info("CNC client initialized (connection managed by ConnectionManager)")
        logger.info("Job monitor initialized (will start with application)")
        logger.info("Startup timing: JobMonitor created in %.1fms", (time.perf_counter() - job_monitor_start) * 1000)

        message_monitor_start = time.perf_counter()
        self.cnc_message_service = CncMessageService(
            self.cnc_client,
            poll_interval_ms=settings.cnc_message_poll_interval_ms,
        )
        logger.info(
            "CNC message monitor initialized (poll interval: %sms)",
            settings.cnc_message_poll_interval_ms,
        )
        logger.info(
            "Startup timing: CncMessageService created in %.1fms",
            (time.perf_counter() - message_monitor_start) * 1000,
        )

        physical_button_start = time.perf_counter()
        self.physical_button_service = PhysicalButtonService(
            self.cnc_client,
            poll_interval_ms=settings.physical_button_poll_interval_ms,
        )
        logger.info(
            "Physical button monitor initialized (poll interval: %sms)",
            settings.physical_button_poll_interval_ms,
        )
        logger.info(
            "Startup timing: PhysicalButtonService created in %.1fms",
            (time.perf_counter() - physical_button_start) * 1000,
        )
        logger.info("Startup timing: AppState init completed in %.1fms", (time.perf_counter() - init_start) * 1000)

        # Safety net: disconnect even on unhandled crashes
        atexit.register(self.cnc_client.disconnect)

    def _auto_start_cnc_server(self) -> None:
        """Launch CncServer.exe on startup if it exists and isn't already running."""
        auto_start_begin = time.perf_counter()
        if self.settings.dev_mode or not self.settings.auto_start_cnc_server:
            logger.info(
                "Auto-start CncServer skipped: dev_mode=%s auto_start_cnc_server=%s",
                self.settings.dev_mode,
                self.settings.auto_start_cnc_server,
            )
            return
        if self.settings.auto_start_eding_gui and not self._defer_gui_to_manual_launcher:
            logger.info("Skipping direct CncServer auto-start because Eding GUI auto-start is enabled")
            return

        cnc_server_exe = cnc_server_path_from_dll(self.settings.dll_path)
        logger.info("Auto-start CncServer check: dll_path=%s cnc_server_exe=%s", self.settings.dll_path, cnc_server_exe)

        if not os.path.isfile(cnc_server_exe):
            logger.warning("Auto-start: CncServer.exe not found at %s", cnc_server_exe)
            logger.info("Startup timing: CncServer auto-start skipped after %.1fms", (time.perf_counter() - auto_start_begin) * 1000)
            return

        result = start_cnc_server_if_needed(str(cnc_server_exe))
        logger.info(
            "Startup timing: start_cnc_server_if_needed returned in %.1fms status=%s pid=%s message=%s",
            (time.perf_counter() - auto_start_begin) * 1000,
            result.status,
            result.pid,
            result.message,
        )
        if result.started:
            logger.info("Auto-started CncServer.exe from %s", cnc_server_exe)
        elif result.already_running:
            logger.info("Auto-start skipped because CncServer.exe is already running")
        else:
            logger.error("Auto-start CncServer.exe failed: %s", result.message)

    def _restart_adapter_after_cnc_server_loss(self) -> None:
        """Restart the adapter so CNC DLL state is recreated after CncServer exits."""
        if self.settings.dev_mode:
            logger.info("DEV_MODE: restarting only CncServer.exe after CNC server loss")
            self._auto_start_cnc_server()
            return

        logger.warning(
            "CncServer.exe disappeared after adapter startup; restarting adapter to refresh CNC DLL state"
        )
        try:
            recovery_start = time.perf_counter()
            request_adapter_recovery_restart()
            logger.warning(
                "Recovery timing: restart script request returned in %.1fms",
                (time.perf_counter() - recovery_start) * 1000,
            )
        except Exception:
            logger.exception("Could not request adapter recovery restart; falling back to CncServer restart")
            self._auto_start_cnc_server()
            return

        logger.warning("Adapter recovery restart requested after CNC server loss; exiting current process")
        os._exit(1)

    def _auto_start_eding_gui(self) -> bool:
        """Launch Eding GUI first when it should own the interactive CNC session."""
        gui_start = time.perf_counter()
        if self.settings.dev_mode or not self.settings.auto_start_eding_gui:
            logger.info(
                "Auto-start Eding GUI skipped: dev_mode=%s auto_start_eding_gui=%s",
                self.settings.dev_mode,
                self.settings.auto_start_eding_gui,
            )
            return False
        if self._defer_gui_to_manual_launcher:
            logger.info("Eding GUI auto-start deferred to START-CNC feedback launcher")
            return False
        result = start_eding_gui_if_needed(self.settings.dll_path, self.settings.task_username)
        logger.info(
            "Startup timing: start_eding_gui_if_needed returned %s in %.1fms",
            result,
            (time.perf_counter() - gui_start) * 1000,
        )
        return result

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
        logger.info("Startup event: CNC ready callback invoked")
        if self.settings.auto_start_eding_gui:
            logger.info("Startup event: CNC ready callback skipped operator message because Eding GUI auto-start is enabled")
            return

        if self.settings.show_operator_ready_message:
            logger.info("Startup event: operator ready popup suppressed; START-CNC splash/feedback handles readiness")

    def start(self) -> None:
        start_begin = time.perf_counter()
        logger.info("Startup timing: AppState.start begin")
        gui_started = self._auto_start_eding_gui()
        if not gui_started:
            self._auto_start_cnc_server()
            manager_start = time.perf_counter()
            self.connection_manager.start()
            logger.info("Startup timing: ConnectionManager.start returned in %.1fms", (time.perf_counter() - manager_start) * 1000)
        else:
            logger.info("Startup timing: scheduling delayed ConnectionManager start after Eding GUI")
            asyncio.create_task(self._start_connection_manager_after_gui_delay())

        monitor_start = time.perf_counter()
        asyncio.create_task(self.job_monitor.start_monitoring())
        logger.info("Job monitor started - watching for job state changes")
        logger.info("Startup timing: JobMonitor start task scheduled in %.1fms", (time.perf_counter() - monitor_start) * 1000)

        message_monitor_start = time.perf_counter()
        asyncio.create_task(self.cnc_message_service.start_monitoring())
        logger.info("CNC message monitor started - watching Eding FIFO messages")
        logger.info("Startup timing: CncMessageService start task scheduled in %.1fms", (time.perf_counter() - message_monitor_start) * 1000)

        physical_button_start = time.perf_counter()
        asyncio.create_task(self.physical_button_service.start_monitoring())
        logger.info("Physical button monitor started - watching RUN/PAUSE inputs")
        logger.info("Startup timing: PhysicalButtonService start task scheduled in %.1fms", (time.perf_counter() - physical_button_start) * 1000)
        logger.info("Startup timing: AppState.start completed in %.1fms gui_started=%s", (time.perf_counter() - start_begin) * 1000, gui_started)

    async def _start_connection_manager_after_gui_delay(self) -> None:
        delay = min(max(self.settings.cnc_retry_interval * 2, 10), 30)
        logger.info("Waiting %ds for Eding GUI/CncServer startup before connecting", delay)
        await asyncio.sleep(delay)
        self.connection_manager.start()

    async def shutdown(self) -> None:
        shutdown_start = time.perf_counter()
        watchdog = threading.Timer(5.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()

        if self.job_monitor is not None and self.job_monitor.is_monitoring:
            logger.info("Stopping job monitor...")
            await self.job_monitor.stop_monitoring()

        if self.physical_button_service is not None and self.physical_button_service.is_monitoring:
            logger.info("Stopping physical button monitor...")
            await self.physical_button_service.stop_monitoring()

        if self.cnc_message_service is not None and self.cnc_message_service.is_monitoring:
            logger.info("Stopping CNC message monitor...")
            await self.cnc_message_service.stop_monitoring()

        logger.info("Disconnecting CNC client...")
        self.cnc_client.disconnect()
        logger.info("Stopping ConnectionManager...")
        await self.connection_manager.stop()
        self._remove_pid_file()
        logger.info("Shutdown complete")
        logger.info("Shutdown timing: AppState shutdown completed in %.1fms", (time.perf_counter() - shutdown_start) * 1000)

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
