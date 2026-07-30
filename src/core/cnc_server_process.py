"""Helpers for idempotently starting the CNC server process."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PROCESS_NAME = "CncServer.exe"


@dataclass(frozen=True)
class CncServerStartResult:
    status: str
    pid: int | None = None
    message: str = ""

    @property
    def started(self) -> bool:
        return self.status == "started"

    @property
    def already_running(self) -> bool:
        return self.status == "already_running"

    @property
    def ok(self) -> bool:
        return self.status in {"started", "already_running"}


def is_cnc_server_running() -> bool:
    """Return True when CncServer.exe is already running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {PROCESS_NAME}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=5,
        )
    except Exception as exc:
        logger.debug("Could not check %s process state: %s", PROCESS_NAME, exc)
        return False

    if result.returncode != 0:
        logger.debug(
            "tasklist failed while checking %s: %s",
            PROCESS_NAME,
            (result.stderr or result.stdout).strip(),
        )
        return False

    return PROCESS_NAME in result.stdout


def stop_cnc_server_if_running() -> bool:
    """Stop CncServer.exe if it is running."""
    if not is_cnc_server_running():
        logger.info("%s is not running; nothing to stop", PROCESS_NAME)
        return False

    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/IM", PROCESS_NAME],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Could not stop %s: %s", PROCESS_NAME, exc)
        return False

    if result.returncode != 0:
        logger.warning("taskkill failed while stopping %s: %s", PROCESS_NAME, (result.stderr or result.stdout).strip())
        return False

    logger.info("Stopped %s", PROCESS_NAME)
    return True


def restart_cnc_server(cnc_server_exe: str) -> CncServerStartResult:
    """Force-restart CncServer.exe, then start a fresh instance."""
    stop_cnc_server_if_running()
    return start_cnc_server_if_needed(cnc_server_exe)


def start_cnc_server_if_needed(cnc_server_exe: str) -> CncServerStartResult:
    """Start CncServer.exe only when it is not already running."""
    if is_cnc_server_running():
        message = f"{PROCESS_NAME} is already running; not starting another instance"
        logger.info(message)
        return CncServerStartResult(status="already_running", message=message)

    cnc_dir = os.path.dirname(cnc_server_exe)
    logger.info("Starting CNC Server: %s", cnc_server_exe)

    try:
        process = subprocess.Popen(
            [cnc_server_exe],
            cwd=cnc_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        message = f"Failed to start CNC Server: {exc}"
        logger.error(message, exc_info=True)
        return CncServerStartResult(status="failed", message=message)

    logger.info("CNC Server started with PID: %d", process.pid)
    return CncServerStartResult(status="started", pid=process.pid, message="CNC Server started")