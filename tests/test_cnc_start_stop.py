"""Tests for POST /api/cnc/start and POST /api/cnc/stop.

These endpoints interact with the OS (subprocess, taskkill), so we test
the HTTP-level behavior with mocked system calls.
"""

import pytest
from unittest.mock import patch, MagicMock


pytestmark = pytest.mark.asyncio


class TestCncStart:

    @patch("src.api.cnc_start.os.path.isfile", return_value=False)
    async def test_start_missing_exe_returns_404(self, mock_isfile, client):
        resp = await client.post("/api/cnc/start")

        assert resp.status_code == 404
        body = resp.json()
        assert "not found" in body["error"].lower()

    @patch("src.api.cnc_start.subprocess.Popen")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_success_redirects(self, mock_isfile, mock_popen, client):
        proc = MagicMock()
        proc.poll.return_value = None  # still running
        proc.pid = 1234
        mock_popen.return_value = proc

        resp = await client.post("/api/cnc/start", follow_redirects=False)

        assert resp.status_code == 303
        assert resp.headers["location"] == "/"

    @patch("src.api.cnc_start.subprocess.Popen")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_process_exits_immediately(self, mock_isfile, mock_popen, client):
        proc = MagicMock()
        proc.poll.return_value = 1  # exited
        proc.returncode = 1
        proc.pid = 1234
        mock_popen.return_value = proc

        resp = await client.post("/api/cnc/start")

        assert resp.status_code == 500
        body = resp.json()
        assert "exited immediately" in body["error"].lower()

    @patch("src.api.cnc_start.subprocess.Popen", side_effect=OSError("access denied"))
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_popen_exception(self, mock_isfile, mock_popen, client):
        resp = await client.post("/api/cnc/start")

        assert resp.status_code == 500
        body = resp.json()
        assert "failed to start" in body["error"].lower()

    @patch("src.api.cnc_start.subprocess.Popen")
    @patch("src.api.cnc_start.os.path.isfile", return_value=True)
    async def test_start_nudges_connection_manager(
        self, mock_isfile, mock_popen, client, connection_manager
    ):
        """After starting CncServer, the handler should nudge the manager."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.pid = 1234
        mock_popen.return_value = proc

        await client.post("/api/cnc/start", follow_redirects=False)

        # The nudge event should have been set
        assert connection_manager._nudge_event.is_set()


class TestCncStop:

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_disconnects_and_redirects(self, mock_ctypes, client, fake_client):
        fake_client._connected = True
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 42

        resp = await client.post("/api/cnc/stop", follow_redirects=False)

        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
        assert fake_client._connected is False

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_shell_execute_failure(self, mock_ctypes, client, fake_client):
        """ShellExecuteW returning <= 32 means failure — should still redirect."""
        fake_client._connected = True
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 2  # failure code

        resp = await client.post("/api/cnc/stop", follow_redirects=False)

        assert resp.status_code == 303
        assert fake_client._connected is False

    @patch("src.api.cnc_stop.ctypes")
    async def test_stop_targets_both_processes(self, mock_ctypes, client, fake_client):
        """Stop should call ShellExecuteW for both cnc.exe and CncServer.exe."""
        fake_client._connected = True
        mock_ctypes.windll.shell32.ShellExecuteW.return_value = 42

        await client.post("/api/cnc/stop", follow_redirects=False)

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

        resp = await client.post("/api/cnc/stop", follow_redirects=False)

        assert resp.status_code == 303

    async def test_get_stop_returns_405(self, client):
        resp = await client.get("/api/cnc/stop")
        assert resp.status_code == 405

    async def test_get_start_returns_405(self, client):
        resp = await client.get("/api/cnc/start")
        assert resp.status_code == 405