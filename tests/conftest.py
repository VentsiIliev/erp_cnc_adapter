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


# ---------------------------------------------------------------------------
# Mock CNC client that satisfies CncClientProtocol
# ---------------------------------------------------------------------------

class FakeCncClient:
    """In-memory fake that mimics CncClientProtocol without any DLL calls."""

    def __init__(self):
        self._connected = False
        self._state = 1  # Idle
        self._job_status = _default_job_status()
        self._load_job_rc = 0
        self._run_job_rc = 0
        self._connect_rc = 0
        self._server_connected = True
        self._server_process_alive = True

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

    def load_job(self, file_name: str) -> int:
        return self._load_job_rc

    def run_job(self) -> int:
        return self._run_job_rc


def _default_job_status() -> dict:
    return {
        "jobName": "test_part.nc",
        "jobLoadCounter": 1,
        "numLinesInJob": 200,
        "numLinesInMacro": 0,
        "numLinesInUserMacro": 0,
        "isLongJob": 0,
        "isSuperLongJob": 0,
        "jobIsRendered": 1,
        "totalJobLength": 150.5,
        "jobProgress": 45.0,
        "jobActualRunningTime": 30.0,
        "jobRemainingRunningTime": 20.0,
        "jobEstimatedTime": 50.0,
        "TCACollision": 0,
        "MCACollision": 0,
        "xCollision": 0,
        "yCollision": 0,
        "zCollision": 0,
        "jobRenderLine": 100,
        "jobRenderProgressPercentage": 50.0,
        "curIpLine": 100,
        "curExLine": 99,
        "lastKnownExecutedLineNumber": 99,
        "lastKnownToolChangeLineNumber": 10,
        "doRepeatJob": 0,
        "nrOfJobRepeatsSet": 0,
        "nrOfRepeatsActual": 0,
        "extraLineWhenEndOfJob": "",
        "stockDiameterTurning": 0.0,
        "stockLengthTurning": 0.0,
        "stockZAtWorkOffset": 0,
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
    )


@pytest.fixture()
def connection_manager(fake_client, settings):
    """Return a ConnectionManager wired to the fake client (not started)."""
    return ConnectionManager(fake_client, settings)


def _build_test_app(fake_client: FakeCncClient, manager: ConnectionManager) -> FastAPI:
    """Create a FastAPI app with injected fakes instead of real CNC hardware."""
    app = FastAPI()
    app.include_router(api_router)

    # Wire up app.state.services so dependency injection works
    services = MagicMock()
    services.cnc_client = fake_client
    services.connection_manager = manager
    app.state.services = services
    return app


@pytest.fixture()
def test_app(fake_client, connection_manager):
    """FastAPI test application with mocked services."""
    return _build_test_app(fake_client, connection_manager)


@pytest.fixture()
async def client(test_app):
    """Async httpx client for making requests against the test app."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac