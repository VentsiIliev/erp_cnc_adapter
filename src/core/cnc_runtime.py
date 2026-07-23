"""CNC runtime path, GUI, and operator notification helpers."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

CNC_SERVER_EXE = "CncServer.exe"
EDING_GUI_CANDIDATES = ("cnc4.03.exe", "cnc.exe")
GUI_TASK_NAME = "ERPCNCAdapterStartEdingGUI"
READY_MESSAGE_TASK_NAME = "ERPCNCAdapterReadyMessage"


def cnc_install_dir_from_dll(dll_path: str) -> Path:
    """Return the CNC install directory derived from the configured cncapi.dll."""
    return Path(dll_path).expanduser().resolve().parent


def cnc_server_path_from_dll(dll_path: str) -> Path:
    return cnc_install_dir_from_dll(dll_path) / CNC_SERVER_EXE


def find_eding_gui_path(dll_path: str) -> Path | None:
    """Find the Eding GUI executable in the same folder as the configured DLL."""
    cnc_dir = cnc_install_dir_from_dll(dll_path)
    for name in EDING_GUI_CANDIDATES:
        candidate = cnc_dir / name
        if candidate.is_file():
            return candidate
    return None


def is_process_running(process_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=5,
        )
    except Exception as exc:
        logger.debug("Could not check %s process state: %s", process_name, exc)
        return False

    return result.returncode == 0 and process_name in result.stdout


def stop_cnc_server_process() -> bool:
    """Stop an existing CncServer.exe before letting Eding GUI own startup."""
    if not is_process_running(CNC_SERVER_EXE):
        return True

    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/IM", CNC_SERVER_EXE],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
    except Exception:
        logger.exception("Failed to stop existing %s before GUI startup", CNC_SERVER_EXE)
        return False

    if result.returncode != 0:
        logger.warning(
            "Failed to stop existing %s before GUI startup: %s",
            CNC_SERVER_EXE,
            (result.stderr or result.stdout).strip(),
        )
        return False

    logger.info("Stopped existing %s before Eding GUI startup", CNC_SERVER_EXE)
    return True


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _start_gui_via_interactive_task(gui_path: Path, task_username: str) -> bool:
    """Ask Task Scheduler to launch the GUI in the configured user's session."""
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$action = New-ScheduledTaskAction -Execute '{_ps_quote(str(gui_path))}' "
        f"-WorkingDirectory '{_ps_quote(str(gui_path.parent))}'\n"
        f"$principal = New-ScheduledTaskPrincipal -UserId '{_ps_quote(task_username)}' "
        "-LogonType Interactive -RunLevel Highest\n"
        "$settings = New-ScheduledTaskSettingsSet "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
        f"Register-ScheduledTask -TaskName '{GUI_TASK_NAME}' "
        "-Action $action -Principal $principal -Settings $settings "
        "-Force | Out-Null\n"
        f"Start-ScheduledTask -TaskName '{GUI_TASK_NAME}'\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = handle.name

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    if result.returncode != 0:
        logger.warning(
            "Interactive Eding GUI task failed for %s: %s",
            task_username,
            (result.stderr or result.stdout).strip(),
        )
        return False

    logger.info("Started Eding GUI through interactive task for %s: %s", task_username, gui_path)
    return True


def _show_message_via_interactive_task(
    machine_number: str,
    adapter_address: str,
    task_username: str,
) -> bool:
    """Show the ready message in the configured user's interactive session."""
    title = "ERP-CNC Adapter ready"
    message = (
        f"Machine {machine_number} is connected and ready.`n"
        f"Adapter API: {adapter_address}"
    )
    command = (
        "Add-Type -AssemblyName PresentationFramework; "
        f"[System.Windows.MessageBox]::Show('{_ps_quote(message)}', "
        f"'{_ps_quote(title)}', 'OK', 'Information') | Out-Null"
    )
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$action = New-ScheduledTaskAction -Execute 'powershell.exe' "
        f"-Argument '-NoProfile -WindowStyle Hidden -Command \"{_ps_quote(command)}\"'\n"
        f"$principal = New-ScheduledTaskPrincipal -UserId '{_ps_quote(task_username)}' "
        "-LogonType Interactive -RunLevel Highest\n"
        "$settings = New-ScheduledTaskSettingsSet "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
        f"Register-ScheduledTask -TaskName '{READY_MESSAGE_TASK_NAME}' "
        "-Action $action -Principal $principal -Settings $settings "
        "-Force | Out-Null\n"
        f"Start-ScheduledTask -TaskName '{READY_MESSAGE_TASK_NAME}'\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = handle.name

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    if result.returncode != 0:
        logger.warning(
            "Interactive ready message task failed for %s: %s",
            task_username,
            (result.stderr or result.stdout).strip(),
        )
        return False

    logger.info("Showed operator ready message through interactive task for %s", task_username)
    return True


def start_eding_gui_if_needed(dll_path: str, task_username: str = "") -> bool:
    """Start Eding GUI from the configured CNC folder when it is not already running."""
    gui_path = find_eding_gui_path(dll_path)
    if gui_path is None:
        logger.warning("Eding GUI executable not found next to configured DLL: %s", dll_path)
        return False

    if is_process_running(gui_path.name):
        logger.info("%s is already running; not starting another GUI instance", gui_path.name)
        return True

    stop_cnc_server_process()

    if os.name == "nt" and task_username.strip():
        if _start_gui_via_interactive_task(gui_path, task_username.strip()):
            return True
        logger.warning("Falling back to direct Eding GUI launch after interactive task failure")

    try:
        subprocess.Popen(
            [str(gui_path)],
            cwd=str(gui_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        logger.exception("Failed to start Eding GUI: %s", gui_path)
        return False

    logger.info("Started Eding GUI: %s", gui_path)
    return True


def show_operator_ready_message(
    machine_number: str,
    adapter_address: str,
    task_username: str = "",
) -> None:
    """Show a short non-critical desktop message when running in a user session."""
    title = "ERP-CNC Adapter ready"
    message = (
        f"Machine {machine_number} is connected and ready.\n"
        f"Adapter API: {adapter_address}"
    )

    if os.name == "nt" and task_username.strip():
        if _show_message_via_interactive_task(
            machine_number,
            adapter_address,
            task_username.strip(),
        ):
            return
        logger.warning("Falling back to direct ready message after interactive task failure")

    def _show() -> None:
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
        except Exception:
            logger.exception("Failed to show operator ready message")

    if os.name != "nt":
        logger.info("%s: %s", title, message.replace("\n", " "))
        return

    threading.Thread(target=_show, name="operator-ready-message", daemon=True).start()
