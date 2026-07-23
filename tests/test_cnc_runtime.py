from pathlib import Path
from unittest.mock import MagicMock, patch


def test_start_eding_gui_uses_interactive_task_for_task_user(tmp_path):
    from src.core.cnc_runtime import start_eding_gui_if_needed

    gui = tmp_path / "cnc.exe"
    gui.write_text("", encoding="utf-8")

    result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("src.core.cnc_runtime.find_eding_gui_path", return_value=gui), \
         patch("src.core.cnc_runtime.is_process_running", side_effect=[False, False]), \
         patch("src.core.cnc_runtime.subprocess.run", return_value=result) as mock_run, \
         patch("src.core.cnc_runtime.subprocess.Popen") as mock_popen:
        assert start_eding_gui_if_needed(str(tmp_path / "cncapi.dll"), r"DOMAIN\adapter") is True

    assert mock_run.call_count == 1
    mock_popen.assert_not_called()


def test_start_eding_gui_falls_back_to_direct_launch_without_task_user(tmp_path):
    from src.core.cnc_runtime import start_eding_gui_if_needed

    gui = tmp_path / "cnc.exe"
    gui.write_text("", encoding="utf-8")

    with patch("src.core.cnc_runtime.find_eding_gui_path", return_value=gui), \
         patch("src.core.cnc_runtime.is_process_running", side_effect=[False, False]), \
         patch("src.core.cnc_runtime.subprocess.Popen") as mock_popen:
        assert start_eding_gui_if_needed(str(tmp_path / "cncapi.dll"), "") is True

    mock_popen.assert_called_once_with(
        [str(gui)],
        cwd=str(Path(gui).parent),
        stdout=-3,
        stderr=-3,
    )


def test_start_eding_gui_stops_existing_server_before_launch(tmp_path):
    from src.core.cnc_runtime import start_eding_gui_if_needed

    gui = tmp_path / "cnc.exe"
    gui.write_text("", encoding="utf-8")
    kill_result = MagicMock(returncode=0, stdout="", stderr="")

    with patch("src.core.cnc_runtime.find_eding_gui_path", return_value=gui), \
         patch("src.core.cnc_runtime.is_process_running", side_effect=[False, True]), \
         patch("src.core.cnc_runtime.subprocess.run", return_value=kill_result) as mock_run, \
         patch("src.core.cnc_runtime.subprocess.Popen"):
        assert start_eding_gui_if_needed(str(tmp_path / "cncapi.dll"), "") is True

    assert mock_run.call_args.args[0] == ["taskkill", "/F", "/T", "/IM", "CncServer.exe"]


def test_start_eding_gui_does_not_stop_server_when_gui_already_running(tmp_path):
    from src.core.cnc_runtime import start_eding_gui_if_needed

    gui = tmp_path / "cnc.exe"
    gui.write_text("", encoding="utf-8")

    with patch("src.core.cnc_runtime.find_eding_gui_path", return_value=gui), \
         patch("src.core.cnc_runtime.is_process_running", return_value=True), \
         patch("src.core.cnc_runtime.subprocess.run") as mock_run, \
         patch("src.core.cnc_runtime.subprocess.Popen") as mock_popen:
        assert start_eding_gui_if_needed(str(tmp_path / "cncapi.dll"), "") is True

    mock_run.assert_not_called()
    mock_popen.assert_not_called()


def test_ready_message_uses_interactive_task_for_task_user():
    from src.core.cnc_runtime import show_operator_ready_message

    result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("src.core.cnc_runtime.subprocess.run", return_value=result) as mock_run, \
         patch("src.core.cnc_runtime.threading.Thread") as mock_thread:
        show_operator_ready_message("CNC9", "192.168.2.86:8002", r"DOMAIN\adapter")

    mock_run.assert_called_once()
    mock_thread.assert_not_called()
