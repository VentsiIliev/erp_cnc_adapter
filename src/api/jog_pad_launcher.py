"""Endpoint and helper for opening the desktop jog pad from the adapter."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class JogPadLaunchResponse(BaseModel):
    status: int
    message: str
    pid: Optional[int] = None
    command: list[str] = Field(default_factory=list)


def _adapter_base_url(request: Request) -> str:
    services = getattr(request.app.state, "services", None)
    settings = getattr(services, "settings", None)
    port = int(getattr(settings, "port", 8002))
    return f"http://127.0.0.1:{port}"


def _jog_pad_command(adapter_url: str, pause_hold_interval_ms: int = 0) -> list[str]:
    pause_args = ["--pause-hold-interval-ms", str(max(0, int(pause_hold_interval_ms)))]
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve()), "--jog-pad", "--adapter-url", adapter_url, *pause_args]

    project_root = Path(__file__).resolve().parents[2]
    jog_pad_script = project_root / "src" / "jog_pad" / "jog_pad.py"
    return [sys.executable, str(jog_pad_script), "--adapter-url", adapter_url, *pause_args]


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def launch_jog_pad(adapter_url: str, pause_hold_interval_ms: int = 0) -> JogPadLaunchResponse:
    command = _jog_pad_command(adapter_url, pause_hold_interval_ms)

    try:
        process = subprocess.Popen(
            command,
            cwd=str(Path(command[0]).resolve().parent),
            close_fds=True,
            creationflags=_creation_flags(),
        )
    except Exception as exc:
        logger.exception("Failed to launch jog pad")
        return JogPadLaunchResponse(
            status=1,
            message=f"Failed to launch jog pad: {exc}",
            command=command,
        )

    logger.info("Jog pad launch requested: pid=%s", process.pid)
    return JogPadLaunchResponse(
        status=0,
        message="Jog pad launch requested",
        pid=process.pid,
        command=command,
    )


@router.post("/api/jog-pad/open", response_model=JogPadLaunchResponse)
async def open_jog_pad(request: Request) -> JogPadLaunchResponse:
    adapter_url = _adapter_base_url(request)
    services = getattr(request.app.state, "services", None)
    settings = getattr(services, "settings", None)
    pause_hold_interval_ms = int(getattr(settings, "jog_pad_pause_hold_interval_ms", 0))
    launcher = getattr(services, "jog_pad_launcher", launch_jog_pad)
    return launcher(adapter_url, pause_hold_interval_ms)
