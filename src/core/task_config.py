"""Scheduled task account helpers for the adapter launcher."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path


TASK_NAME = "ERPCNCAdapter"
WATCHDOG_TASK_NAME = "ERPCNCAdapterWatchdog"
DEFAULT_STARTUP_DELAY_SECONDS = 90

logger = logging.getLogger(__name__)

def _startupinfo() -> subprocess.STARTUPINFO:
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return info


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _seconds_to_iso8601_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours}H")
    if minutes:
        parts.append(f"{minutes}M")
    if remaining_seconds or not parts:
        parts.append(f"{remaining_seconds}S")
    return "PT" + "".join(parts)


def _parse_iso8601_duration_seconds(value: str) -> int:
    value = (value or "").upper().strip()
    if not value.startswith("PT"):
        return 0
    number = ""
    total = 0
    for char in value[2:]:
        if char.isdigit():
            number += char
            continue
        if not number:
            continue
        amount = int(number)
        number = ""
        if char == "H":
            total += amount * 3600
        elif char == "M":
            total += amount * 60
        elif char == "S":
            total += amount
    return total


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
        "$logonType = $task.Principal.LogonType\n"
        "$enabled = $task.State -ne 'Disabled'\n"
        "$triggerDelay = ''\n"
        "if ($task.Triggers.Count -gt 0 -and $task.Triggers[0].Delay) { $triggerDelay = [string]$task.Triggers[0].Delay }\n"
        "$result = @{ userId = $userId; logonType = $logonType; enabled = $enabled; delay = $triggerDelay }\n"
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
    logon_type = str(payload.get("logonType") or "").strip()
    auto_start_enabled = bool(payload.get("enabled", True))
    startup_delay_seconds = _parse_iso8601_duration_seconds(str(payload.get("delay") or ""))
    if not user_id or user_id.upper() == "SYSTEM":
        return {
            "task_username": "",
            "run_as_windows_user": False,
            "task_password_configured": False,
            "auto_start_adapter_on_logon": auto_start_enabled,
            "adapter_startup_delay_seconds": startup_delay_seconds,
        }

    return {
        "task_username": user_id,
        "run_as_windows_user": True,
        "task_password_configured": logon_type.lower() not in {"interactive", "interactivetoken"},
        "auto_start_adapter_on_logon": auto_start_enabled,
        "adapter_startup_delay_seconds": startup_delay_seconds,
    }


def configure_task_launch_account(
    task_username: str = "",
    task_password: str = "",
    auto_start_enabled: bool = True,
    startup_delay_seconds: int = DEFAULT_STARTUP_DELAY_SECONDS,
) -> dict[str, object]:
    """Re-register startup tasks to run as SYSTEM or a specific Windows account."""
    install_dir = _resolve_install_dir()
    exe_path = _resolve_exe_path(install_dir)
    watchdog_path = install_dir / "scripts" / "watchdog.bat"
    watchdog_launcher_path = install_dir / "scripts" / "watchdog_hidden.vbs"

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "schtasks /Delete /TN 'ERPCNCAdapter' /F *> $null\n"
        "schtasks /Delete /TN 'ERPCNCAdapterWatchdog' /F *> $null\n"
        f"$installDir = '{_ps_quote(str(install_dir))}'\n"
        f"$exePath = '{_ps_quote(str(exe_path))}'\n"
        f"$watchdogPath = '{_ps_quote(str(watchdog_path))}'\n"
        f"$watchdogLauncherPath = '{_ps_quote(str(watchdog_launcher_path))}'\n"
        "$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $installDir\n"
        f"$startupDelay = '{_seconds_to_iso8601_duration(startup_delay_seconds)}'\n"
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)\n"
    )

    if task_username:
        script += (
            f"$taskUser = '{_ps_quote(task_username)}'\n"
            "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser\n"
            "$trigger.Delay = $startupDelay\n"
        )
        if task_password:
            script += (
                f"$taskPassword = '{_ps_quote(task_password)}'\n"
                f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings "
                "-User $taskUser -Password $taskPassword -RunLevel Highest -Force | Out-Null\n"
            )
        else:
            script += (
                "$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
                f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null\n"
            )
    else:
        script += (
            "$trigger = New-ScheduledTaskTrigger -AtStartup\n"
            "$trigger.Delay = $startupDelay\n"
            "$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
            f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null\n"
        )

    script += (
        "if (Test-Path $watchdogPath) {\n"
        "  $watchdogDir = Split-Path -Parent $watchdogPath\n"
        "  $watchdogVbs = @(\n"
        "    'Set shell = CreateObject(\"WScript.Shell\")',\n"
        "    ('shell.CurrentDirectory = \"' + $watchdogDir.Replace('\"', '\"\"') + '\"'),\n"
        "    ('shell.Run \"cmd.exe /c \"\"' + $watchdogPath.Replace('\"', '\"\"') + '\"\"\", 0, False')\n"
        "  )\n"
        "  Set-Content -LiteralPath $watchdogLauncherPath -Value $watchdogVbs -Encoding UTF8\n"
        "  $watchdogAction = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('\"' + $watchdogLauncherPath + '\"') -WorkingDirectory $installDir\n"
        "  $watchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)\n"
        "  $watchdogSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
    )

    if task_username:
        script += "  if ($taskPassword) {\n"
        script += (
            f"    Register-ScheduledTask -TaskName '{WATCHDOG_TASK_NAME}' -Action $watchdogAction -Trigger $watchdogTrigger -Settings $watchdogSettings "
            "-User $taskUser -Password $taskPassword -RunLevel Highest -Force | Out-Null\n"
        )
        script += "  } else {\n"
        script += (
            "    $watchdogPrincipal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
            f"    Register-ScheduledTask -TaskName '{WATCHDOG_TASK_NAME}' -Action $watchdogAction -Trigger $watchdogTrigger -Principal $watchdogPrincipal -Settings $watchdogSettings -Force | Out-Null\n"
        )
        script += "  }\n"
    else:
        script += (
            "  $watchdogPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
            f"  Register-ScheduledTask -TaskName '{WATCHDOG_TASK_NAME}' -Action $watchdogAction -Trigger $watchdogTrigger -Principal $watchdogPrincipal -Settings $watchdogSettings -Force | Out-Null\n"
        )

    script += "}\n"
    if not auto_start_enabled:
        script += (
            f"Disable-ScheduledTask -TaskName '{TASK_NAME}' | Out-Null\n"
            f"Disable-ScheduledTask -TaskName '{WATCHDOG_TASK_NAME}' -ErrorAction SilentlyContinue | Out-Null\n"
        )

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
        "task_password_configured": bool(task_username.strip() and task_password),
        "auto_start_adapter_on_logon": auto_start_enabled,
        "adapter_startup_delay_seconds": max(0, int(startup_delay_seconds)),
    }


def set_adapter_autostart_enabled(enabled: bool) -> None:
    """Enable or disable scheduled startup tasks without changing their account."""
    command = "/Enable" if enabled else "/Disable"
    for task_name in (TASK_NAME, WATCHDOG_TASK_NAME):
        result = subprocess.run(
            ["schtasks", "/Change", "/TN", task_name, command],
            capture_output=True,
            text=True,
            startupinfo=_startupinfo(),
        )
        if result.returncode != 0 and task_name == TASK_NAME:
            raise RuntimeError((result.stderr or result.stdout).strip() or "Failed to update adapter startup task.")


def restart_scheduled_adapter_task() -> None:
    """Ask Windows Task Scheduler to run the adapter task, falling back to a direct launch."""
    result = subprocess.run(
        ["schtasks", "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        startupinfo=_startupinfo(),
    )
    if result.returncode == 0:
        return

    install_dir = _resolve_install_dir()
    exe_path = _resolve_exe_path(install_dir)
    subprocess.Popen(
        [str(exe_path)],
        cwd=str(install_dir),
        close_fds=True,
        startupinfo=_startupinfo(),
    )


def request_adapter_recovery_restart() -> None:
    """Launch the installed restart script to reset adapter, GUI, and CncServer."""
    install_dir = _resolve_install_dir()
    restart_script = install_dir / "scripts" / "restart.bat"
    logger.warning("Recovery restart requested: install_dir=%s restart_script=%s", install_dir, restart_script)
    if not restart_script.exists():
        logger.warning("Recovery restart script missing; falling back to scheduled adapter task restart")
        restart_scheduled_adapter_task()
        return

    env = os.environ.copy()
    env["ERPCNC_MANUAL_TASK"] = "1"
    env["ERPCNC_SHOW_SPLASH"] = "0"
    subprocess.Popen(
        ["cmd.exe", "/c", "call", str(restart_script)],
        cwd=str(restart_script.parent),
        close_fds=True,
        env=env,
        startupinfo=_startupinfo(),
    )
    logger.warning("Recovery restart script launched: %s", restart_script)
