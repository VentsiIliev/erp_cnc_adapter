"""
Compatibility entry point for the standalone PyQt5 desktop jog pad.

The implementation is split across MVC-style modules in this package, but this
file stays launchable so existing dashboard and installer commands can continue
calling src\jog_pad\jog_pad.py directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)

from src.jog_pad.app import JogPadWindow, _install_jog_pad_ipc_server, _parse_args, _signal_existing_jog_pad, main
from src.jog_pad.client import AdapterJogClient
from src.jog_pad.config import (
    ACCENT_BLUE,
    FALLBACK_ADAPTER_PORT,
    JOG_DIRECTION_ICONS,
    JOG_PAD_IPC_PREFIX,
    POSITION_ERROR_DISPLAY_THRESHOLD,
    POSITION_POLL_INTERVAL_MS,
    POSITION_READ_TIMEOUT_SECONDS,
    STEP_MODE_ICONS,
    THEME,
    JogPadTheme,
    jog_pad_ipc_server_name,
    resolve_adapter_url,
    resolve_home_icon_path,
    resolve_icon_path,
    resolve_jogpad_icon_path,
    resolve_reset_icon_path,
    resolve_resource_path,
)
from src.jog_pad.pad import JogPad
from src.jog_pad.widgets import (
    ArrowJogButton,
    BitmapCommandButton,
    CloseButton,
    CoordinateReadout,
    CustomStepButton,
    HomeStatusButton,
    StepModeButton,
    ZeroAxisButton,
)
from src.jog_pad.workers import BackgroundCommandSender, CncMessagePoller, CoordinatePoller, PauseHoldThread

__all__ = [
    "ACCENT_BLUE",
    "FALLBACK_ADAPTER_PORT",
    "JOG_DIRECTION_ICONS",
    "JOG_PAD_IPC_PREFIX",
    "POSITION_ERROR_DISPLAY_THRESHOLD",
    "POSITION_POLL_INTERVAL_MS",
    "POSITION_READ_TIMEOUT_SECONDS",
    "STEP_MODE_ICONS",
    "THEME",
    "AdapterJogClient",
    "ArrowJogButton",
    "BackgroundCommandSender",
    "BitmapCommandButton",
    "CloseButton",
    "CoordinatePoller",
    "CoordinateReadout",
    "CustomStepButton",
    "HomeStatusButton",
    "JogPad",
    "JogPadTheme",
    "JogPadWindow",
    "PauseHoldThread",
    "StepModeButton",
    "ZeroAxisButton",
    "_install_jog_pad_ipc_server",
    "_parse_args",
    "_signal_existing_jog_pad",
    "jog_pad_ipc_server_name",
    "main",
    "resolve_adapter_url",
    "resolve_home_icon_path",
    "resolve_icon_path",
    "resolve_jogpad_icon_path",
    "resolve_reset_icon_path",
    "resolve_resource_path",
]


if __name__ == "__main__":
    raise SystemExit(main())
