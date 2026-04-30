"""Scheduled task account helpers for the adapter launcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


TASK_NAME = "ERPCNCAdapter"
WATCHDOG_TASK_NAME = "ERPCNCAdapterWatchdog"


def _startupinfo() -> subprocess.STARTUPINFO:
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return info


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _resolve_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _resolve_exe_path(install_dir: Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    dist_exe = install_dir / "dist" / "erp-cnc-adapter.exe"
    if dist_exe.exists():
        return dist_exe

    raise FileNotFoundError(
        f"Could not locate erp-cnc-adapter.exe. Checked: {dist_exe}"
    )


def get_task_launch_settings() -> dict[str, object]:
    """Return the current scheduled-task launch account for the adapter."""
    script = (
        "$task = Get-ScheduledTask -TaskName 'ERPCNCAdapter' -ErrorAction Stop\n"
        "$userId = $task.Principal.UserId\n"
        "$result = @{ userId = $userId }\n"
        "$result | ConvertTo-Json -Compress\n"
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        startupinfo=_startupinfo(),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "Could not query scheduled task.")

    payload = json.loads(result.stdout.strip() or "{}")
    user_id = str(payload.get("userId") or "").strip()
    if not user_id or user_id.upper() == "SYSTEM":
        return {
            "task_username": "",
            "run_as_windows_user": False,
            "task_password_configured": False,
        }

    return {
        "task_username": user_id,
        "run_as_windows_user": True,
        "task_password_configured": True,
    }


def configure_task_launch_account(task_username: str = "", task_password: str = "") -> dict[str, object]:
    """Re-register startup tasks to run as SYSTEM or a specific Windows account."""
    install_dir = _resolve_install_dir()
    exe_path = _resolve_exe_path(install_dir)
    watchdog_path = install_dir / "scripts" / "watchdog.bat"

    if task_username and not task_password:
        raise ValueError("A Windows password is required when configuring a scheduled task account.")

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "schtasks /Delete /TN 'ERPCNCAdapter' /F *> $null\n"
        "schtasks /Delete /TN 'ERPCNCAdapterWatchdog' /F *> $null\n"
        f"$installDir = '{_ps_quote(str(install_dir))}'\n"
        f"$exePath = '{_ps_quote(str(exe_path))}'\n"
        f"$watchdogPath = '{_ps_quote(str(watchdog_path))}'\n"
        "$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $installDir\n"
        "$trigger = New-ScheduledTaskTrigger -AtStartup\n"
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)\n"
    )

    if task_username:
        script += (
            f"$taskUser = '{_ps_quote(task_username)}'\n"
            f"$taskPassword = '{_ps_quote(task_password)}'\n"
            f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -User $taskUser -Password $taskPassword -RunLevel Highest -Force | Out-Null\n"
        )
    else:
        script += (
            "$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
            f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null\n"
        )

    script += (
        "if (Test-Path $watchdogPath) {\n"
        "  $watchdogAction = New-ScheduledTaskAction -Execute $watchdogPath -WorkingDirectory $installDir\n"
        "  $watchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)\n"
        "  $watchdogSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
    )

    if task_username:
        script += (
            f"  Register-ScheduledTask -TaskName '{WATCHDOG_TASK_NAME}' -Action $watchdogAction -Trigger $watchdogTrigger -Settings $watchdogSettings -User $taskUser -Password $taskPassword -RunLevel Highest -Force | Out-Null\n"
        )
    else:
        script += (
            "  $watchdogPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
            f"  Register-ScheduledTask -TaskName '{WATCHDOG_TASK_NAME}' -Action $watchdogAction -Trigger $watchdogTrigger -Principal $watchdogPrincipal -Settings $watchdogSettings -Force | Out-Null\n"
        )

    script += "}\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = handle.name

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True,
            text=True,
            startupinfo=_startupinfo(),
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "Failed to update scheduled tasks.")

    return {
        "task_username": task_username.strip(),
        "run_as_windows_user": bool(task_username.strip()),
        "task_password_configured": bool(task_username.strip()),
    }


def restart_scheduled_adapter_task() -> None:
    """Ask Windows Task Scheduler to run the adapter task immediately."""
    result = subprocess.run(
        ["schtasks", "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        startupinfo=_startupinfo(),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "Failed to restart scheduled task.")
