"""Tests for GET /api/cnc/start and GET /api/cnc/stop.

These endpoints interact with the OS (subprocess, taskkill), so we test
the HTTP-level behavior with mocked system calls.
"""

import pytest
from unittest.mock import patch

from src.core.cnc_server_process import CncServerStartResult


pytestmark = pytest.mark.asyncio


class TestCncStart:

    @patch("src.api.cnc_start.os.path.isfile", return_value=False)
    async def test_start_missing_exe_returns_404(self, mock_isfile, client):
        resp = await client.get("/api/cnc/start")

        assert resp.status_code == 404
        body = resp.json()
        assert "not found" in body["error"].lower()

    @patch("src.api.cnc_start.start_cnc_server_if_needed")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_success_redirects(self, mock_isfile, mock_start, client):
        mock_start.return_value = CncServerStartResult(status="started", pid=1234)

        resp = await client.get("/api/cnc/start", follow_redirects=False)

        assert resp.status_code == 303
        assert resp.headers["location"] == "/"

    @patch("src.api.cnc_start.start_cnc_server_if_needed")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_helper_failure(self, mock_isfile, mock_start, client):
        mock_start.return_value = CncServerStartResult(status="failed", message="boom")

        resp = await client.get("/api/cnc/start")

        assert resp.status_code == 500
        body = resp.json()
        assert "boom" in body["error"].lower()

    @patch("src.api.cnc_start.start_cnc_server_if_needed")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_nudges_connection_manager(
        self, mock_isfile, mock_start, client, connection_manager
    ):
        """After starting CncServer, the handler should nudge the manager."""
        mock_start.return_value = CncServerStartResult(status="started", pid=1234)

        await client.get("/api/cnc/start", follow_redirects=False)

        assert connection_manager._nudge_event.is_set()

    @patch("src.api.cnc_start.start_cnc_server_if_needed")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_already_running_redirects_without_spawning(
        self, mock_isfile, mock_start, client, connection_manager
    ):
        mock_start.return_value = CncServerStartResult(status="already_running")

        resp = await client.get("/api/cnc/start", follow_redirects=False)

        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
        assert connection_manager._nudge_event.is_set()

class TestCncStop:

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_disconnects_and_redirects(self, mock_ctypes, client, fake_client):
        fake_client._connected = True
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 42

        resp = await client.get("/api/cnc/stop", follow_redirects=False)

        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
        assert fake_client._connected is False

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_shell_execute_failure(self, mock_ctypes, client, fake_client):
        """ShellExecuteW returning <= 32 means failure — should still redirect."""
        fake_client._connected = True
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 2  # failure code

        resp = await client.get("/api/cnc/stop", follow_redirects=False)

        assert resp.status_code == 303
        assert fake_client._connected is False

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_targets_both_processes(self, mock_ctypes, client, fake_client):
        """Stop should call ShellExecuteW for both cnc.exe and CncServer.exe."""
        fake_client._connected = True
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 42

        await client.get("/api/cnc/stop", follow_redirects=False)

        calls = mock_ctypes.windll.shell32.ShellExecuteW.call_args_list
        assert len(calls) == 2
        args_strs = [str(c) for c in calls]
        assert any("cnc.exe" in s for s in args_strs)
        assert any("CncServer.exe" in s for s in args_strs)

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_already_disconnected(self, mock_ctypes, client, fake_client):
        """Stop should work even when client is already disconnected."""
        fake_client._connected = False
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 42

        resp = await client.get("/api/cnc/stop", follow_redirects=False)

        assert resp.status_code == 303

