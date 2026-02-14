"""
Windows Service for ERP-CNC Adapter (EXE Mode)
Runs dist/erp-cnc-adapter.exe as a Windows service.
"""

import logging
import os
import sys
import subprocess

import win32serviceutil
import win32service
import win32event
import servicemanager

# Paths - service is in windows_service/, find EXE in parent directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Try to find EXE in multiple locations (dev vs distribution)
EXE_NAME = "erp-cnc-adapter.exe"
if os.path.exists(os.path.join(PROJECT_ROOT, EXE_NAME)):
    # Distribution mode - EXE is in parent directory
    EXE_PATH = os.path.join(PROJECT_ROOT, EXE_NAME)
else:
    # Development mode - EXE is in dist/ folder
    EXE_PATH = os.path.join(PROJECT_ROOT, "dist", EXE_NAME)

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "service.log")

# Setup logging
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class ERPCNCAdapterService(win32serviceutil.ServiceFramework):
    """Windows Service for ERP-CNC Adapter."""

    _svc_name_ = "ERPCNCAdapter"
    _svc_display_name_ = "ERP-CNC Adapter Service"
    _svc_description_ = "REST API service for CNC machine control. Auto-starts on boot."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = False
        self.process = None
        logger.info(f"Service initialized - EXE: {EXE_PATH}")

    def SvcStop(self):
        """Stop the service."""
        logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.is_running = False

        if self.process:
            try:
                logger.info("Terminating adapter process...")
                self.process.terminate()
                self.process.wait(timeout=10)
                logger.info("Process terminated successfully")
            except subprocess.TimeoutExpired:
                logger.warning("Forcing process kill...")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping process: {e}")

    def SvcDoRun(self):
        """Start the service."""
        logger.info("Service starting")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        self.is_running = True
        self.run_adapter()

    def run_adapter(self):
        """Run the adapter EXE."""
        try:
            # Check if EXE exists
            if not os.path.exists(EXE_PATH):
                error_msg = f"EXE not found: {EXE_PATH}"
                logger.error(error_msg)
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_ERROR_TYPE,
                    servicemanager.PYS_SERVICE_STOPPED,
                    (self._svc_name_, error_msg)
                )
                return

            logger.info(f"Starting adapter: {EXE_PATH}")

            # Start EXE without console window
            # The service will hide the window even though console=True in the spec
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # Don't pipe stdout/stderr - let the app handle its own logging
            self.process = subprocess.Popen(
                [EXE_PATH],
                cwd=PROJECT_ROOT,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            logger.info(f"Adapter started (PID: {self.process.pid})")

            # Monitor process
            while self.is_running:
                # Check for stop signal
                rc = win32event.WaitForSingleObject(self.stop_event, 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break

                # Check if process crashed
                if self.process.poll() is not None:
                    return_code = self.process.returncode
                    logger.error(f"Adapter process crashed with code: {return_code}")
                    servicemanager.LogMsg(
                        servicemanager.EVENTLOG_ERROR_TYPE,
                        servicemanager.PYS_SERVICE_STOPPED,
                        (self._svc_name_, f"Process crashed: {return_code}")
                    )
                    break

            # Cleanup
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()

            logger.info("Service stopped")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, "")
            )

        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_ERROR_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, f"Error: {str(e)}")
            )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ERPCNCAdapterService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ERPCNCAdapterService)

