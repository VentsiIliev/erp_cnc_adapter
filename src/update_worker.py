"""
Detached update worker.

Spawned by /api/update. It survives adapter shutdown and applies either:
- legacy single-EXE updates, or
- full ZIP update packages containing manifest.json and the installed payload.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("update_worker")

PRESERVE_PATTERNS = (
    "config.json",
    "adapter.pid",
    ".update-lock",
    "logs/*",
    "backups/*",
    "staged-update.*",
    "scripts/*.vbs",
    "scripts/start_cnc_feedback.ps1",
    "scripts/start_eding_handoff.ps1",
)


def check_installation_type(service_name: str) -> str:
    result = subprocess.run(["sc", "query", service_name], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return "service"
    result = subprocess.run(["schtasks", "/Query", "/TN", service_name], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return "task"
    return "unknown"


def stop_adapter(service_name: str, exe_name: str, install_type: str) -> bool:
    if install_type == "service":
        logger.info("Detected Windows Service installation; stopping %s", service_name)
        result = subprocess.run(["net", "stop", service_name], capture_output=True, text=True, timeout=30)
        logger.info("stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            logger.warning("stderr: %s", result.stderr.strip())
        return True
    logger.info("Detected %s installation; adapter process will be stopped by launcher PID and exact executable path", install_type)
    return True


def start_adapter(service_name: str, install_type: str, exe_path: str = "") -> bool:
    if install_type == "service":
        result = subprocess.run(["net", "start", service_name], capture_output=True, text=True, timeout=30)
        logger.info("stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            logger.warning("stderr: %s", result.stderr.strip())
            return False
        return True

    if install_type == "task":
        logger.info("Starting scheduled task %s", service_name)
        result = subprocess.run(["schtasks", "/Run", "/TN", service_name], capture_output=True, text=True, timeout=30)
        logger.info("stdout: %s", result.stdout.strip())
        if result.returncode == 0:
            return True
        logger.warning("stderr: %s", result.stderr.strip())
        logger.warning("Scheduled task start failed; falling back to direct launch")

    if not exe_path or not os.path.exists(exe_path):
        logger.error("EXE path not available or missing: %s", exe_path)
        return False

    exe_dir = os.path.dirname(exe_path)
    try:
        create_new_process_group = 0x00000200
        detached_process = 0x00000008
        subprocess.Popen(
            [exe_path],
            cwd=exe_dir,
            creationflags=create_new_process_group | detached_process,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as exc:
        logger.error("Failed to launch EXE: %s", exc)
        return False


def get_exe_version(exe_path: str) -> str:
    version_file = os.path.join(os.path.dirname(exe_path), "VERSION.txt")
    if os.path.exists(version_file):
        try:
            import re
            text = Path(version_file).read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"(\d+\.\d+\.\d+)", text)
            if match:
                return match.group(1)
        except OSError:
            pass
    return "unknown"


def _normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _is_preserved(relative_path: str) -> bool:
    normalized = _normalize_zip_name(relative_path)
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in PRESERVE_PATTERNS)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(package_path: str) -> dict:
    with zipfile.ZipFile(package_path, "r") as archive:
        try:
            with archive.open("manifest.json") as handle:
                return json.loads(handle.read().decode("utf-8"))
        except KeyError as exc:
            raise RuntimeError("Update package is missing manifest.json") from exc


def _validate_zip_entry(name: str) -> str:
    normalized = _normalize_zip_name(name)
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        raise RuntimeError(f"Unsafe path in update package: {name}")
    drive, _ = os.path.splitdrive(normalized)
    if drive:
        raise RuntimeError(f"Absolute path in update package: {name}")
    return normalized


def _verify_package(package_path: str, manifest: dict) -> None:
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError("Update manifest has no files list")

    expected = {}
    for item in files:
        path = _normalize_zip_name(str(item.get("path", "")))
        sha256 = str(item.get("sha256", "")).lower()
        if not path or not sha256:
            raise RuntimeError("Update manifest contains an invalid file entry")
        expected[path] = sha256

    if "erp-cnc-adapter.exe" not in expected:
        raise RuntimeError("Update package does not contain erp-cnc-adapter.exe")

    with zipfile.ZipFile(package_path, "r") as archive:
        names = {_validate_zip_entry(info.filename) for info in archive.infolist() if not info.is_dir()}
        for path, expected_hash in expected.items():
            if path not in names:
                raise RuntimeError(f"Update package is missing {path}")
            with archive.open(path) as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            if digest.lower() != expected_hash:
                raise RuntimeError(f"Checksum mismatch for {path}")


def _manifest_file_set(manifest: dict) -> set[str]:
    return {_normalize_zip_name(str(item.get("path", ""))) for item in manifest.get("files", []) if item.get("path")} | {"manifest.json"}


def _zip_file_set(package_path: str) -> set[str]:
    with zipfile.ZipFile(package_path, "r") as archive:
        return {_validate_zip_entry(info.filename) for info in archive.infolist() if not info.is_dir()}


def _remove_obsolete_managed_files(install_dir: str, allowed_files: set[str]) -> None:
    install_root = Path(install_dir)
    for path in sorted(install_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_file():
            continue
        relative = path.relative_to(install_root).as_posix()
        if _is_preserved(relative):
            continue
        if relative in allowed_files:
            continue
        try:
            path.unlink()
            logger.info("Removed obsolete managed file: %s", relative)
        except OSError as exc:
            raise RuntimeError(f"Failed to remove obsolete file {relative}: {exc}") from exc


def _backup_install_dir(install_dir: str, current_version: str) -> str:
    backup_dir = os.path.join(install_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"install-backup-v{current_version}.{timestamp}.zip")
    install_root = Path(install_dir)
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in install_root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(install_root).as_posix()
            if rel == Path(backup_path).relative_to(install_root).as_posix():
                continue
            if rel.startswith("logs/") or rel.startswith("backups/") or rel.startswith("staged-update"):
                continue
            archive.write(path, rel)
    logger.info("Install directory backup created: %s", backup_path)
    return backup_path


def _restore_backup(backup_path: str, install_dir: str) -> None:
    logger.warning("Restoring install backup: %s", backup_path)
    _install_zip_payload(backup_path, install_dir, verify_manifest=False)


def _install_zip_payload(package_path: str, install_dir: str, verify_manifest: bool = True) -> dict:
    manifest = {}
    if verify_manifest:
        manifest = _read_manifest(package_path)
        _verify_package(package_path, manifest)
        allowed_files = _manifest_file_set(manifest)
        logger.info("Verified update package version: %s", manifest.get("version", "unknown"))
    else:
        allowed_files = _zip_file_set(package_path)

    _remove_obsolete_managed_files(install_dir, allowed_files)

    with zipfile.ZipFile(package_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            relative = _validate_zip_entry(info.filename)
            if relative == "manifest.json":
                target = os.path.join(install_dir, relative)
            elif _is_preserved(relative):
                logger.info("Preserving local file from package overwrite: %s", relative)
                continue
            else:
                target = os.path.join(install_dir, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)
    return manifest


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _repair_adapter_hidden_launcher(install_dir: str) -> bool:
    """Repair the legacy adapter VBS launcher for installs that still reference it."""
    install_path = Path(install_dir)
    exe_path = install_path / "erp-cnc-adapter.exe"
    launcher_path = install_path / "scripts" / "launch_adapter_hidden.vbs"
    if os.name != "nt":
        return False
    if not exe_path.exists():
        logger.warning("Adapter hidden launcher repair skipped; adapter EXE is missing: %s", exe_path)
        return False

    def vbs_quote(value: str) -> str:
        return value.replace('"', '""')

    launcher_text = (
        'Set shell = CreateObject("WScript.Shell")\n'
        f'shell.CurrentDirectory = "{vbs_quote(str(install_path))}"\n'
        f'shell.Run """{vbs_quote(str(exe_path))}""", 0, False\n'
    )
    try:
        launcher_path.parent.mkdir(parents=True, exist_ok=True)
        launcher_path.write_text(launcher_text, encoding="utf-8")
    except Exception as exc:
        logger.warning("Adapter hidden launcher repair failed: %s", exc)
        return False

    logger.info("Adapter hidden launcher repaired to start adapter directly: %s", launcher_path)
    return True

def _repair_adapter_scheduled_task_action(install_dir: str) -> bool:
    """Point the main adapter scheduled task directly at erp-cnc-adapter.exe."""
    install_path = Path(install_dir)
    exe_path = install_path / "erp-cnc-adapter.exe"
    if os.name != "nt":
        return False
    if not exe_path.exists():
        logger.warning("Adapter scheduled task repair skipped; adapter EXE is missing: %s", exe_path)
        return False

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "Get-ScheduledTask -TaskName 'ERPCNCAdapter' -ErrorAction Stop | Out-Null\n"
        f"$exePath = '{_ps_quote(str(exe_path))}'\n"
        f"$workDir = '{_ps_quote(str(install_path))}'\n"
        "$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $workDir\n"
        "Set-ScheduledTask -TaskName 'ERPCNCAdapter' -Action $action | Out-Null\n"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("Adapter scheduled task repair failed to run: %s", exc)
        return False

    if result.returncode != 0:
        logger.warning("Adapter scheduled task repair failed: %s", (result.stderr or result.stdout).strip())
        return False

    logger.info("Adapter scheduled task repaired to launch EXE directly: %s", exe_path)
    return True

def _repair_start_cnc_shortcut(install_dir: str) -> bool:
    """Point the desktop START-CNC shortcut at the hidden launcher after updates."""
    launcher_path = Path(install_dir) / "scripts" / "start_cnc_hidden.vbs"
    icon_path = Path(install_dir) / "resources" / "logo.ico"
    if os.name != "nt":
        return False
    if not launcher_path.exists():
        logger.warning("START-CNC shortcut repair skipped; hidden launcher is missing: %s", launcher_path)
        return False

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$desktopCandidates = @()\n"
        "if ($env:PUBLIC) { $desktopCandidates += (Join-Path $env:PUBLIC 'Desktop') }\n"
        "if ($env:USERPROFILE) { $desktopCandidates += (Join-Path $env:USERPROFILE 'Desktop') }\n"
        "$desktop = $desktopCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1\n"
        "if (-not $desktop) { throw 'Could not find a desktop folder for shortcut creation.' }\n"
        "$shortcutPath = Join-Path $desktop 'START-CNC.lnk'\n"
        "$shell = New-Object -ComObject WScript.Shell\n"
        "$shortcut = $shell.CreateShortcut($shortcutPath)\n"
        "$shortcut.TargetPath = 'wscript.exe'\n"
        f"$shortcut.Arguments = '//B //Nologo \"{_ps_quote(str(launcher_path))}\"'\n"
        f"$shortcut.WorkingDirectory = '{_ps_quote(str(launcher_path.parent))}'\n"
        f"$shortcut.IconLocation = '{_ps_quote(str(icon_path))}'\n"
        "$shortcut.Description = 'Start CNC adapter runtime'\n"
        "$shortcut.Save()\n"
        "Write-Output $shortcutPath\n"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        logger.warning("START-CNC shortcut repair failed to run: %s", exc)
        return False

    if result.returncode != 0:
        logger.warning("START-CNC shortcut repair failed: %s", (result.stderr or result.stdout).strip())
        return False

    logger.info("START-CNC shortcut repaired to hidden launcher: %s", result.stdout.strip())
    return True


def _repair_status_indicator_task(install_dir: str) -> bool:
    """Create or repair the independent operator status indicator logon task after updates."""
    script_path = Path(install_dir) / "scripts" / "status_indicator.ps1"
    launcher_path = Path(install_dir) / "scripts" / "status_indicator_hidden.vbs"
    if os.name != "nt":
        return False
    if not script_path.exists():
        logger.warning("Status indicator task repair skipped; script is missing: %s", script_path)
        return False

    launcher_text = (
        'Set shell = CreateObject("WScript.Shell")\n'
        f'shell.CurrentDirectory = "{str(script_path.parent).replace(chr(34), chr(34) + chr(34))}"\n'
        f'shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""{str(script_path).replace(chr(34), chr(34) + chr(34))}""", 0, False\n'
    )
    try:
        launcher_path.write_text(launcher_text, encoding="utf-8")
    except Exception as exc:
        logger.warning("Status indicator launcher repair failed: %s", exc)
        return False

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$installDir = '{_ps_quote(str(install_dir))}'\n"
        "$configPath = Join-Path $installDir 'config.json'\n"
        "$taskUser = ('{0}\\{1}' -f $env:USERDOMAIN, $env:USERNAME)\n"
        "$config = $null\n"
        "if (Test-Path $configPath) { try { $config = Get-Content -Path $configPath -Raw | ConvertFrom-Json } catch {} }\n"
        "if ($config -and $config.task_username) { $taskUser = [string]$config.task_username }\n"
        f"$launcherPath = '{_ps_quote(str(launcher_path))}'\n"
        f"$workDir = '{_ps_quote(str(launcher_path.parent))}'\n"
        "Unregister-ScheduledTask -TaskName 'ERPCNCAdapterStatusIndicator' -Confirm:$false -ErrorAction SilentlyContinue\n"
        "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('//B //Nologo \"' + $launcherPath + '\"') -WorkingDirectory $workDir\n"
        "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser\n"
        "$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
        "Register-ScheduledTask -TaskName 'ERPCNCAdapterStatusIndicator' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null\n"
        "Start-ScheduledTask -TaskName 'ERPCNCAdapterStatusIndicator' -ErrorAction SilentlyContinue\n"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        logger.warning("Status indicator task repair failed to run: %s", exc)
        return False

    if result.returncode != 0:
        logger.warning("Status indicator task repair failed: %s", (result.stderr or result.stdout).strip())
        return False

    logger.info("Status indicator task repaired and started")
    return True


def _stop_status_indicator_processes(install_dir: str) -> None:
    """Stop only the old status indicator PowerShell process so updated scripts take effect."""
    script_path = Path(install_dir) / "scripts" / "status_indicator.ps1"
    if os.name != "nt":
        return

    script = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        f"$target = '{_ps_quote(str(script_path))}'\n"
        "$currentPid = $PID\n"
        "Get-CimInstance Win32_Process -Filter \"Name = 'powershell.exe' OR Name = 'pwsh.exe'\" | "
        "Where-Object { $_.ProcessId -ne $currentPid -and $_.CommandLine -and $_.CommandLine.IndexOf($target, [StringComparison]::OrdinalIgnoreCase) -ge 0 } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Output $_.ProcessId }\n"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Could not stop status indicator process: %s", exc)
        return

    stopped = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if stopped:
        logger.info("Stopped old status indicator process IDs: %s", ", ".join(stopped))
    elif result.returncode != 0:
        logger.warning("Status indicator process stop returned %s: %s", result.returncode, result.stderr.strip())


def _install_legacy_exe(staged_path: str, exe_path: str, current_version: str) -> str:
    exe_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(exe_dir, f"{exe_name}.v{current_version}.bak.{timestamp}")
    if os.path.exists(exe_path):
        shutil.copy2(exe_path, backup_path)
        logger.info("Legacy EXE backup created: %s", backup_path)
    if os.path.exists(exe_path):
        os.remove(exe_path)
    shutil.copy2(staged_path, exe_path)
    os.remove(staged_path)
    return backup_path


def _normalize_path_for_compare(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _parse_wmic_process_lines(output: str, exe_path: str) -> list[int]:
    target = _normalize_path_for_compare(exe_path)
    process_ids: list[int] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("executablepath"):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        executable, pid_text = parts
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if _normalize_path_for_compare(executable) == target:
            process_ids.append(pid)
    return process_ids


def _get_process_ids_for_exe_path_wmic(exe_path: str) -> list[int]:
    if os.name != "nt" or not exe_path:
        return []

    exe_name = os.path.basename(exe_path)
    try:
        result = subprocess.run(
            ["wmic", "process", "where", f"name='{exe_name}'", "get", "ProcessId,ExecutablePath"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Could not enumerate adapter processes through WMIC for %s: %s", exe_path, exc)
        return []

    if result.returncode != 0:
        logger.warning("Adapter process enumeration through WMIC failed: %s", result.stderr.strip())
        return []

    return _parse_wmic_process_lines(result.stdout, exe_path)


def _get_process_ids_for_exe_path(exe_path: str) -> list[int]:
    if os.name != "nt" or not exe_path:
        return []

    script = (
        "$target = [Console]::In.ReadToEnd().Trim(); "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ExecutablePath -eq $target } | "
        "ForEach-Object { [string]$_.ProcessId }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            input=exe_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Could not enumerate adapter processes through PowerShell for %s: %s", exe_path, exc)
        return _get_process_ids_for_exe_path_wmic(exe_path)

    if result.returncode != 0:
        logger.warning("Adapter process enumeration through PowerShell failed: %s", result.stderr.strip())
        return _get_process_ids_for_exe_path_wmic(exe_path)

    process_ids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            process_ids.append(int(line))
        except ValueError:
            logger.debug("Ignoring non-numeric process id from enumeration: %s", line)
    return process_ids


def _kill_process_id(pid: int) -> bool:
    try:
        result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, timeout=10)
    except Exception as exc:
        logger.warning("Could not kill adapter pid=%s: %s", pid, exc)
        return False

    if result.returncode == 0:
        logger.info("Killed lingering adapter process pid=%s: %s", pid, result.stdout.strip())
        return True

    logger.info("Adapter pid=%s was not running or could not be killed: %s", pid, result.stderr.strip())
    return False


def _wait_until_exe_unlocked(exe_path: str, timeout_seconds: float = 30.0) -> None:
    if not exe_path or not os.path.exists(exe_path):
        return

    deadline = time.monotonic() + timeout_seconds
    probe_path = f"{exe_path}.update-probe"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            os.replace(exe_path, probe_path)
            os.replace(probe_path, exe_path)
            logger.info("Adapter executable is unlocked and replaceable: %s", exe_path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)

    raise RuntimeError(f"Adapter executable is still locked after {timeout_seconds:.0f}s: {exe_path}: {last_error}")


def _stop_processes(exe_name: str, exe_path: str = "", adapter_pid: int | None = None) -> None:
    logger.info("Waiting 2 seconds for adapter to exit before force check")
    time.sleep(2)

    current_pid = os.getpid()
    killed_any = False
    killed_pids: set[int] = set()

    if adapter_pid and adapter_pid != current_pid:
        if _kill_process_id(adapter_pid):
            killed_any = True
        killed_pids.add(adapter_pid)
    elif adapter_pid == current_pid:
        logger.warning("Skipping adapter process kill because target pid is update worker pid=%s", current_pid)

    if exe_path:
        for pid in _get_process_ids_for_exe_path(exe_path):
            if pid == current_pid or pid in killed_pids:
                logger.info("Skipping adapter pid=%s because it is current worker or already handled", pid)
                continue
            if _kill_process_id(pid):
                killed_any = True
            killed_pids.add(pid)
    else:
        logger.warning("No adapter exe path provided; skipping process scan for %s", exe_name)

    if killed_any:
        time.sleep(1)

    _wait_until_exe_unlocked(exe_path)

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ERP-CNC Adapter update worker")
    parser.add_argument("--exe-path", required=True, help="Path to the current EXE")
    parser.add_argument("--staged-path", required=True, help="Path to the staged update package or EXE")
    parser.add_argument("--service-name", default="ERPCNCAdapter", help="Windows service/task name")
    parser.add_argument("--package-kind", choices=("auto", "exe", "zip", "restore"), default="auto")
    parser.add_argument("--adapter-pid", type=int, default=0, help="PID of adapter process that launched this worker")
    args = parser.parse_args(argv)

    exe_path = args.exe_path
    staged_path = args.staged_path
    service_name = args.service_name
    install_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)
    package_kind = args.package_kind
    adapter_pid = args.adapter_pid or None
    if package_kind == "auto":
        package_kind = "zip" if staged_path.lower().endswith(".zip") else "exe"

    log_dir = os.path.join(install_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "update.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    current_version = get_exe_version(exe_path)
    staged_size_mb = round(os.path.getsize(staged_path) / (1024 * 1024), 2) if os.path.exists(staged_path) else 0
    install_type = check_installation_type(service_name)
    lock_file = os.path.join(install_dir, ".update-lock")

    logger.info("=" * 70)
    logger.info("ERP-CNC ADAPTER UPDATE PROCESS STARTED")
    logger.info("Current version: %s", current_version)
    logger.info("Package kind: %s", package_kind)
    logger.info("Staged path: %s (%.2f MB)", staged_path, staged_size_mb)
    logger.info("Install dir: %s", install_dir)
    logger.info("Installation type: %s", install_type)
    logger.info("Launcher adapter PID: %s; update worker PID: %s", adapter_pid, os.getpid())
    logger.info("=" * 70)

    try:
        Path(lock_file).write_text(f"Update in progress since {datetime.now():%Y-%m-%d %H:%M:%S}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not create lock file: %s", exc)

    backup_path = ""
    try:
        stop_adapter(service_name, exe_name, install_type)
        _stop_processes(exe_name, exe_path, adapter_pid)

        if package_kind == "zip":
            logger.info("Installing full update package")
            backup_path = _backup_install_dir(install_dir, current_version)
            _install_zip_payload(staged_path, install_dir, verify_manifest=True)
            _repair_adapter_hidden_launcher(install_dir)
            _repair_adapter_scheduled_task_action(install_dir)
            _repair_start_cnc_shortcut(install_dir)
            _stop_status_indicator_processes(install_dir)
            _repair_status_indicator_task(install_dir)
            os.remove(staged_path)
        elif package_kind == "restore":
            logger.info("Restoring full install backup package")
            _install_zip_payload(staged_path, install_dir, verify_manifest=False)
            os.remove(staged_path)
        else:
            logger.info("Installing legacy EXE update")
            backup_path = _install_legacy_exe(staged_path, exe_path, current_version)

        if not start_adapter(service_name, install_type, exe_path):
            raise RuntimeError("Adapter failed to start after update")

        logger.info("UPDATE COMPLETED SUCCESSFULLY")
        logger.info("Backup created: %s", backup_path)
    except Exception as exc:
        logger.error("UPDATE FAILED: %s", exc)
        if package_kind == "zip" and backup_path and os.path.exists(backup_path):
            try:
                _restore_backup(backup_path, install_dir)
                start_adapter(service_name, install_type, exe_path)
                logger.info("Rollback from full backup completed")
            except Exception as rollback_exc:
                logger.error("CRITICAL: rollback failed: %s", rollback_exc)
        raise SystemExit(1) from exc
    finally:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Lock file removed")
        except OSError as exc:
            logger.warning("Could not remove lock file: %s", exc)


if __name__ == "__main__":
    main()
