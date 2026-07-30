"""Tests for CNC server process helpers."""

from unittest.mock import MagicMock, patch

from src.core.cnc_server_process import (
    CncServerStartResult,
    is_cnc_server_running,
    restart_cnc_server,
    start_cnc_server_if_needed,
    stop_cnc_server_if_running,
)


def test_is_cnc_server_running_detects_tasklist_match():
    result = MagicMock()
    result.returncode = 0
    result.stdout = '"CncServer.exe","1234","Console","1","12,345 K"'

    with patch("src.core.cnc_server_process.subprocess.run", return_value=result):
        assert is_cnc_server_running() is True


def test_is_cnc_server_running_returns_false_without_match():
    result = MagicMock()
    result.returncode = 0
    result.stdout = "INFO: No tasks are running which match the specified criteria."

    with patch("src.core.cnc_server_process.subprocess.run", return_value=result):
        assert is_cnc_server_running() is False


def test_start_cnc_server_if_needed_skips_when_already_running():
    with patch("src.core.cnc_server_process.is_cnc_server_running", return_value=True), \
         patch("src.core.cnc_server_process.subprocess.Popen") as mock_popen:
        result = start_cnc_server_if_needed(r"C:\CNC\CncServer.exe")

    assert result == CncServerStartResult(
        status="already_running",
        message="CncServer.exe is already running; not starting another instance",
    )
    mock_popen.assert_not_called()


def test_start_cnc_server_if_needed_starts_when_not_running():
    process = MagicMock()
    process.pid = 1234

    with patch("src.core.cnc_server_process.is_cnc_server_running", return_value=False), \
         patch("src.core.cnc_server_process.subprocess.Popen", return_value=process) as mock_popen:
        result = start_cnc_server_if_needed(r"C:\CNC\CncServer.exe")

    assert result.status == "started"
    assert result.pid == 1234
    mock_popen.assert_called_once()


def test_start_cnc_server_if_needed_returns_failure():
    with patch("src.core.cnc_server_process.is_cnc_server_running", return_value=False), \
         patch("src.core.cnc_server_process.subprocess.Popen", side_effect=OSError("access denied")):
        result = start_cnc_server_if_needed(r"C:\CNC\CncServer.exe")

    assert result.status == "failed"
    assert "access denied" in result.message

def test_stop_cnc_server_if_running_stops_existing_process():
    result = MagicMock()
    result.returncode = 0
    result.stdout = "SUCCESS"
    result.stderr = ""

    with patch("src.core.cnc_server_process.is_cnc_server_running", return_value=True), \
         patch("src.core.cnc_server_process.subprocess.run", return_value=result) as mock_run:
        assert stop_cnc_server_if_running() is True

    mock_run.assert_called_once_with(
        ["taskkill", "/F", "/T", "/IM", "CncServer.exe"],
        capture_output=True,
        text=True,
        creationflags=mock_run.call_args.kwargs["creationflags"],
        timeout=10,
    )


def test_stop_cnc_server_if_running_skips_when_not_running():
    with patch("src.core.cnc_server_process.is_cnc_server_running", return_value=False), \
         patch("src.core.cnc_server_process.subprocess.run") as mock_run:
        assert stop_cnc_server_if_running() is False

    mock_run.assert_not_called()


def test_restart_cnc_server_stops_then_starts():
    with patch("src.core.cnc_server_process.stop_cnc_server_if_running") as mock_stop, \
         patch("src.core.cnc_server_process.start_cnc_server_if_needed", return_value=CncServerStartResult(status="started", pid=42)) as mock_start:
        result = restart_cnc_server(r"C:\CNC\CncServer.exe")

    mock_stop.assert_called_once_with()
    mock_start.assert_called_once_with(r"C:\CNC\CncServer.exe")
    assert result.started is True
