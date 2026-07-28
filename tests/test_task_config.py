from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core import task_config
from src.core.task_config import (
    _parse_iso8601_duration_seconds,
    _seconds_to_iso8601_duration,
    configure_task_launch_account,
    request_adapter_recovery_restart,
    restart_scheduled_adapter_task,
    set_adapter_autostart_enabled,
)


def _completed(returncode: int = 0, stderr: str = "", stdout: str = ""):
    return SimpleNamespace(returncode=returncode, stderr=stderr, stdout=stdout)


def test_set_adapter_autostart_enabled_disables_main_and_watchdog_tasks():
    with patch("src.core.task_config.subprocess.run", return_value=_completed()) as mock_run:
        set_adapter_autostart_enabled(False)

    commands = [call.args[0] for call in mock_run.call_args_list]
    assert commands == [
        ["schtasks", "/Change", "/TN", "ERPCNCAdapter", "/Disable"],
        ["schtasks", "/Change", "/TN", "ERPCNCAdapterWatchdog", "/Disable"],
    ]


def test_set_adapter_autostart_enabled_raises_when_main_task_update_fails():
    with patch("src.core.task_config.subprocess.run", return_value=_completed(returncode=1, stderr="Access denied")):
        with pytest.raises(RuntimeError, match="Access denied"):
            set_adapter_autostart_enabled(True)


def test_restart_scheduled_adapter_task_falls_back_to_direct_launch_when_task_disabled(tmp_path):
    exe_path = tmp_path / "erp-cnc-adapter.exe"
    exe_path.write_text("", encoding="utf-8")

    with patch("src.core.task_config.subprocess.run", return_value=_completed(returncode=1, stderr="Task disabled")) as mock_run, \
         patch("src.core.task_config._resolve_install_dir", return_value=tmp_path), \
         patch("src.core.task_config._resolve_exe_path", return_value=exe_path), \
         patch("src.core.task_config.subprocess.Popen") as mock_popen:
        restart_scheduled_adapter_task()

    mock_run.assert_called_once()
    mock_popen.assert_called_once_with(
        [str(exe_path)],
        cwd=str(tmp_path),
        close_fds=True,
        startupinfo=mock_popen.call_args.kwargs["startupinfo"],
    )


def test_request_adapter_recovery_restart_launches_restart_script(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    restart_script = scripts_dir / "restart.bat"
    restart_script.write_text("@echo off\n", encoding="utf-8")

    with patch("src.core.task_config._resolve_install_dir", return_value=tmp_path), \
         patch("src.core.task_config.subprocess.Popen") as mock_popen, \
         patch("src.core.task_config.restart_scheduled_adapter_task") as mock_restart_task:
        request_adapter_recovery_restart()

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == ["cmd.exe", "/c", "call", str(restart_script)]
    assert kwargs["cwd"] == str(scripts_dir)
    assert kwargs["env"]["ERPCNC_MANUAL_TASK"] == "1"
    mock_restart_task.assert_not_called()


def test_request_adapter_recovery_restart_falls_back_to_main_task_when_restart_script_missing(tmp_path):
    with patch("src.core.task_config._resolve_install_dir", return_value=tmp_path), \
         patch("src.core.task_config.subprocess.Popen") as mock_popen, \
         patch("src.core.task_config.restart_scheduled_adapter_task") as mock_restart_task:
        request_adapter_recovery_restart()

    mock_popen.assert_not_called()
    mock_restart_task.assert_called_once_with()

def test_startup_delay_duration_helpers_round_trip_common_values():
    for seconds, duration in ((0, "PT0S"), (45, "PT45S"), (90, "PT1M30S"), (3661, "PT1H1M1S")):
        assert _seconds_to_iso8601_duration(seconds) == duration
        assert _parse_iso8601_duration_seconds(duration) == seconds


def test_configure_task_launch_account_writes_logon_trigger_delay(tmp_path):
    exe_path = tmp_path / "erp-cnc-adapter.exe"
    exe_path.write_text("", encoding="utf-8")
    script_contents = []

    def fake_run(command, **kwargs):
        script_contents.append(task_config.Path(command[-1]).read_text(encoding="utf-8"))
        return _completed()

    with patch("src.core.task_config._resolve_install_dir", return_value=tmp_path), \
         patch("src.core.task_config._resolve_exe_path", return_value=exe_path), \
         patch("src.core.task_config.subprocess.run", side_effect=fake_run):
        result = configure_task_launch_account(
            task_username=r"DOMAIN\adapter",
            task_password="",
            auto_start_enabled=True,
            startup_delay_seconds=90,
        )

    assert result["adapter_startup_delay_seconds"] == 90
    script_text = script_contents[0]
    assert "$startupDelay = 'PT1M30S'" in script_text
    assert "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser" in script_text
    assert "$trigger.Delay = $startupDelay" in script_text
