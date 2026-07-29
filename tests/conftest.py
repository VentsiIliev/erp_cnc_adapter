"""Shared pytest fixtures for the ERP-CNC Adapter test suite.

Provides a mock CNC client, test FastAPI app, and httpx async client
so that tests can run without real CNC hardware or DLLs.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from src.api import api_router
from src.cnc.connection_manager import ConnectionManager
from src.core.config import Settings
from src.api.jog_pad_launcher import JogPadLaunchResponse


# ---------------------------------------------------------------------------
# Mock CNC client that satisfies CncClientProtocol
# ---------------------------------------------------------------------------

class FakeCncClient:
    """In-memory fake that mimics CncClientProtocol without any DLL calls."""

    def __init__(self):
        self._connected = False
        self._state = 2  # Ready (not Idle) - required for load_job and start_job to work
        self._job_status = _default_job_status()
        self._load_job_rc = 0
        self._run_job_rc = 0
        self.run_job_calls = 0
        self._pause_job_rc = 0
        self.pause_job_calls = 0
        self._reset_rc = 0
        self.reset_calls = 0
        self._connect_rc = 0
        self._server_connected = True
        self._server_process_alive = True
        self._all_axes_homed = True
        self._motion_enabled = True
        self._physical_button_status = {
            "runInput": False,
            "pauseInput": False,
            "runRaw": 1,
            "pauseRaw": 1,
            "runLogical": 1,
            "pauseLogical": 0,
        }
        self._home_all_axes_rc = 0
        self.home_all_axes_calls = 0
        self.home_all_axes_gui_calls = 0
        self.loaded_jobs = []
        self.jog_commands = []
        self.stop_jog_commands = []
        self.move_commands = []
        self.zero_commands = []
        self.set_work_coordinate_commands = []
        self._start_jog_rc = 0
        self._stop_jog_rc = 0
        self._move_to_rc = 0
        self._zero_work_axis_rc = 0
        self._set_work_coordinate_rc = 0
        self._last_cnc_message = None
        self.clear_cnc_messages_calls = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> int:
        if self._connect_rc in (0, 6, 7):  # OK, ALREADY_RUNS, ALREADY_CONNECTED
            self._connected = True
        return self._connect_rc

    def disconnect(self) -> None:
        self._connected = False

    def is_server_connected(self) -> bool:
        return self._server_connected

    def is_server_process_alive(self) -> bool:
        return self._server_process_alive

    def get_state(self) -> int:
        return self._state

    def get_job_status(self) -> dict:
        return dict(self._job_status)

    def get_positions(self) -> dict:
        return {
            "work": {"x": 1.25, "y": 2.5, "z": -3.75, "a": 0.0, "b": 0.0, "c": 0.0},
            "machine": {"x": 10.0, "y": 20.0, "z": -30.0, "a": 0.0, "b": 0.0, "c": 0.0},
        }

    def get_physical_button_status(self) -> dict:
        return dict(self._physical_button_status)

    def get_all_axes_homed(self) -> bool:
        return self._all_axes_homed

    def is_motion_enabled(self) -> bool:
        return self._motion_enabled

    def get_last_cnc_message(self) -> str | None:
        return self._last_cnc_message

    def clear_cnc_messages(self) -> None:
        self.clear_cnc_messages_calls += 1
        self._last_cnc_message = None
    def home_all_axes_gui_sequence(self) -> int:
        self.home_all_axes_gui_calls += 1
        return self._home_all_axes_rc


    def home_all_axes_sequence(self) -> int:
        self.home_all_axes_calls += 1
        return self._home_all_axes_rc

    def load_job(self, file_name: str) -> int:
        self.loaded_jobs.append(file_name)
        self._job_status["jobName"] = file_name
        return self._load_job_rc

    def set_job_quantity(self, quantity: int) -> int:
        return 0  # Always succeed in tests

    def render_job(self) -> int:
        return 0  # Always succeed in tests

    def run_job(self) -> int:
        self.run_job_calls += 1
        return self._run_job_rc

    def pause_job(self) -> int:
        self.pause_job_calls += 1
        return self._pause_job_rc

    def reset(self) -> int:
        self.reset_calls += 1
        return self._reset_rc

    def start_jog(
        self,
        axis: str,
        direction: int,
        step: float,
        velocity_factor: float,
        continuous: bool,
    ) -> int:
        self.jog_commands.append({
            "axis": axis,
            "direction": direction,
            "step": step,
            "velocity_factor": velocity_factor,
            "continuous": continuous,
        })
        return self._start_jog_rc

    def stop_jog(self, axis: str | None = None) -> int:
        self.stop_jog_commands.append(axis)
        return self._stop_jog_rc

    def move_to(self, axis: str, position: float, velocity_factor: float) -> int:
        self.move_commands.append({
            "axis": axis,
            "position": position,
            "velocity_factor": velocity_factor,
        })
        return self._move_to_rc

    def zero_work_axis(self, axis: str) -> int:
        self.zero_commands.append(axis)
        return self._zero_work_axis_rc

    def set_work_coordinate(self, axis: str, value: float) -> int:
        self.set_work_coordinate_commands.append({"axis": axis, "value": value})
        return self._set_work_coordinate_rc


def _default_job_status() -> dict:
    return {
        "jobName": "test_part.nc",
        "jobLoadCounter": 1,
        "totalJobLengthMm": 150.5,
        "jobProgressMm": 45.0,
        "jobActualRunningTimeSeconds": 30.0,
        "jobRemainingRunningTimeSeconds": 20.0,
        "jobEstimatedTimeSeconds": 50.0,
        "doRepeatJob": 0,
        "nrOfJobRepeatsSet": 0,
        "nrOfRepeatsActual": 0,
        # Commented out - not currently used
        # "numLinesInJob": 200,
        # "numLinesInMacro": 0,
        # "numLinesInUserMacro": 0,
        # "isLongJob": 0,
        # "isSuperLongJob": 0,
        # "jobIsRendered": 1,
        # "TCACollision": 0,
        # "MCACollision": 0,
        # "xCollision": 0,
        # "yCollision": 0,
        # "zCollision": 0,
        # "jobRenderLine": 100,
        # "jobRenderProgressPercentage": 50.0,
        # "curIpLine": 100,
        # "curExLine": 99,
        # "lastKnownExecutedLineNumber": 99,
        # "lastKnownToolChangeLineNumber": 10,
        # "extraLineWhenEndOfJob": "",
        # "stockDiameterTurning": 0.0,
        # "stockLengthTurning": 0.0,
        # "stockZAtWorkOffset": 0,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_client():
    """Return a fresh FakeCncClient for unit tests."""
    return FakeCncClient()


@pytest.fixture()
def settings():
    """Return test settings (paths are irrelevant since DLL is mocked)."""
    return Settings(
        dll_path=r"C:\fake\cncapi.dll",
        ini_path=r"C:\fake\cnc.ini",
        host="127.0.0.1",
        port=9999,
        log_level="WARNING",
        cnc_retry_interval=1,
        cnc_health_interval=1,
        jog_pad_pause_hold_interval_ms=0,
        base_dir=r"\\192.168.2.11\Production\CNC\Mills",
    )


@pytest.fixture()
def connection_manager(fake_client, settings):
    """Return a ConnectionManager wired to the fake client (not started)."""
    return ConnectionManager(fake_client, settings)


def _build_test_app(fake_client: FakeCncClient, manager: ConnectionManager, settings: Settings) -> FastAPI:
    """Create a FastAPI app with injected fakes instead of real CNC hardware."""
    app = FastAPI()
    app.include_router(api_router)

    # Wire up app.state.services so dependency injection works
    services = MagicMock()
    services.cnc_client = fake_client
    services.connection_manager = manager
    services.settings = settings

    # Add job_monitor mock (no actual monitoring, just for state checks)
    job_monitor_mock = MagicMock()
    job_monitor_mock._was_running = False  # Not running by default
    job_monitor_mock._job_info = {}
    services.job_monitor = job_monitor_mock
    services.physical_button_service = MagicMock()

    # Add last_loaded_job storage
    services.last_loaded_job = None
    services.jog_pad_launcher = MagicMock(return_value=JogPadLaunchResponse(status=0, message="Jog pad launch requested", pid=1234))

    app.state.services = services
    return app


@pytest.fixture()
def test_app(fake_client, connection_manager, settings):
    """FastAPI test application with mocked services."""
    return _build_test_app(fake_client, connection_manager, settings)


@pytest.fixture()
async def client(test_app):
    """Async httpx client for making requests against the test app."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
