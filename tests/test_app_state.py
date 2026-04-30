"""Tests for src/core/app_state.py — AppState lifecycle and PID management."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.core.app_state import _kill_stale_adapter, _write_pid_file, AppState, PID_FILE
from src.core.cnc_server_process import CncServerStartResult


# ---------------------------------------------------------------------------
# PID file management
# ---------------------------------------------------------------------------

class TestWritePidFile:

    def test_writes_current_pid(self, tmp_path):
        pid_file = str(tmp_path / "adapter.pid")
        with patch("src.core.app_state.PID_FILE", pid_file):
            _write_pid_file()
            assert open(pid_file).read().strip() == str(os.getpid())


class TestKillStaleAdapter:

    def test_noop_when_pid_file_missing(self, tmp_path):
        pid_file = str(tmp_path / "no_such.pid")
        with patch("src.core.app_state.PID_FILE", pid_file):
            _kill_stale_adapter()  # should not raise

    def test_noop_when_pid_matches_current(self, tmp_path):
        pid_file = str(tmp_path / "adapter.pid")
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        with patch("src.core.app_state.PID_FILE", pid_file):
            _kill_stale_adapter()  # should not raise or kill

    def test_kills_stale_process(self, tmp_path):
        pid_file = str(tmp_path / "adapter.pid")
        with open(pid_file, "w") as f:
            f.write("99999")
        with patch("src.core.app_state.PID_FILE", pid_file), \
             patch("src.core.app_state.os.kill") as mock_kill:
            _kill_stale_adapter()
            mock_kill.assert_called_once()

    def test_handles_already_dead_process(self, tmp_path):
        pid_file = str(tmp_path / "adapter.pid")
        with open(pid_file, "w") as f:
            f.write("99999")
        with patch("src.core.app_state.PID_FILE", pid_file), \
             patch("src.core.app_state.os.kill", side_effect=OSError("no such process")):
            _kill_stale_adapter()  # should not raise


class TestRemovePidFile:

    def test_removes_file(self, tmp_path):
        pid_file = str(tmp_path / "adapter.pid")
        with open(pid_file, "w") as f:
            f.write("123")
        with patch("src.core.app_state.PID_FILE", pid_file):
            AppState._remove_pid_file()
            assert not os.path.exists(pid_file)

    def test_ignores_missing_file(self, tmp_path):
        pid_file = str(tmp_path / "no_such.pid")
        with patch("src.core.app_state.PID_FILE", pid_file):
            AppState._remove_pid_file()  # should not raise


# ---------------------------------------------------------------------------
# AppState init
# ---------------------------------------------------------------------------

class TestAppStateInit:

    @patch("src.core.app_state._write_pid_file")
    @patch("src.core.app_state._kill_stale_adapter")
    @patch("src.core.app_state.atexit.register")
    def test_dev_mode_creates_mock_client(self, mock_atexit, _kill, _write):
        from src.core.config import Settings
        from src.cnc.mock_cnc_client import MockCncClient

        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        state = AppState(settings)
        assert isinstance(state.cnc_client, MockCncClient)

    @patch("src.core.app_state._write_pid_file")
    @patch("src.core.app_state._kill_stale_adapter")
    @patch("src.core.app_state.atexit.register")
    def test_registers_atexit(self, mock_atexit, _kill, _write):
        from src.core.config import Settings

        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        state = AppState(settings)
        mock_atexit.assert_called_once_with(state.cnc_client.disconnect)

    @patch("src.core.app_state._write_pid_file")
    @patch("src.core.app_state._kill_stale_adapter")
    @patch("src.core.app_state.atexit.register")
    @patch("src.core.app_state.CncClient", side_effect=RuntimeError("Failed to load CNC DLL"))
    def test_falls_back_to_unavailable_client_when_dll_load_fails(
        self, _cnc_client, mock_atexit, _kill, _write
    ):
        from src.core.config import Settings
        from src.cnc.unavailable_cnc_client import UnavailableCncClient

        settings = Settings(
            dll_path=r"C:\missing\cncapi.dll",
            ini_path=r"C:\missing\cnc.ini",
            dev_mode=False,
        )
        state = AppState(settings)
        assert isinstance(state.cnc_client, UnavailableCncClient)
        assert "Failed to load CNC DLL" in state.cnc_client.startup_error


# ---------------------------------------------------------------------------
# AppState lifecycle
# ---------------------------------------------------------------------------

class TestAppStateLifecycle:


    @patch("src.core.app_state.os.path.isfile", return_value=True)
    @patch("src.core.app_state.start_cnc_server_if_needed")
    @patch("src.core.app_state._write_pid_file")
    @patch("src.core.app_state._kill_stale_adapter")
    @patch("src.core.app_state.atexit.register")
    @patch("src.core.app_state.CncClient", side_effect=RuntimeError("DLL unavailable"))
    def test_auto_start_skips_when_cnc_server_already_running(
        self, _cnc_client, _atexit, _kill, _write, mock_start, _isfile
    ):
        from src.core.config import Settings

        mock_start.return_value = CncServerStartResult(status="already_running")
        settings = Settings(
            dll_path=r"C:\CNC\cncapi.dll",
            ini_path=r"C:\CNC\cnc.ini",
            dev_mode=False,
        )
        state = AppState(settings)
        state.connection_manager = MagicMock()
        state.job_monitor = MagicMock()

        state._auto_start_cnc_server()

        mock_start.assert_called_once_with(r"C:\CNC\CncServer.exe")

    @patch("src.core.app_state._write_pid_file")
    @patch("src.core.app_state._kill_stale_adapter")
    @patch("src.core.app_state.atexit.register")
    def test_start_calls_manager_start(self, _atexit, _kill, _write):
        from src.core.config import Settings

        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        state = AppState(settings)
        state.connection_manager = MagicMock()
        state.job_monitor = MagicMock()

        # Mock the start_monitoring method to return a coroutine
        async def mock_start_monitoring():
            pass
        state.job_monitor.start_monitoring = MagicMock(return_value=mock_start_monitoring())

        with patch("asyncio.create_task") as mock_create_task:
            state.start()
            state.connection_manager.start.assert_called_once()
            # Verify job monitor start_monitoring was called via create_task
            mock_create_task.assert_called_once()
            mock_create_task.call_args.args[0].close()

    @patch("src.core.app_state._write_pid_file")
    @patch("src.core.app_state._kill_stale_adapter")
    @patch("src.core.app_state.atexit.register")
    async def test_shutdown_disconnects_and_removes_pid(self, _atexit, _kill, _write):
        from unittest.mock import AsyncMock
        from src.core.config import Settings

        settings = Settings(
            dll_path=r"C:\fake.dll",
            ini_path=r"C:\fake.ini",
            dev_mode=True,
        )
        state = AppState(settings)
        state.connection_manager = MagicMock()
        state.connection_manager.stop = AsyncMock()
        state.job_monitor = MagicMock()
        state.job_monitor.is_monitoring = False

        with patch.object(AppState, "_remove_pid_file") as mock_remove:
            await state.shutdown()
            state.connection_manager.stop.assert_awaited_once()
            mock_remove.assert_called_once()
