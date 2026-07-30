from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt5.QtGui import QColor


ACCENT_BLUE = "#224896"
FALLBACK_ADAPTER_PORT = 8002
POSITION_READ_TIMEOUT_SECONDS = 0.75
POSITION_POLL_INTERVAL_MS = 200
MESSAGE_POLL_INTERVAL_MS = 250
PHYSICAL_BUTTON_POLL_INTERVAL_MS = 50
POSITION_ERROR_DISPLAY_THRESHOLD = 3
JOG_PAD_IPC_PREFIX = "erp_cnc_adapter_jog_pad"


def resolve_resource_path(file_name: str) -> Optional[str]:
    """Locate a resource file for dev and installed runs."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "resources" / file_name)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "resources" / file_name)
    else:
        candidates.append(Path(__file__).resolve().parents[2] / "resources" / file_name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def resolve_icon_path() -> Optional[str]:
    """Locate resources/logo.ico for dev and installed runs."""
    return resolve_resource_path("logo.ico")


def resolve_jogpad_icon_path(file_name: str) -> Optional[str]:
    """Locate an original jog pad bitmap under resources/jogpad."""
    return resolve_resource_path(f"jogpad/{file_name}")


def resolve_home_icon_path() -> Optional[str]:
    """Locate the all-axes home bitmap for dev and installed runs."""
    return resolve_resource_path("home.bmp")


def resolve_reset_icon_path() -> Optional[str]:
    """Locate resources/reset.bmp for dev and installed runs."""
    return resolve_resource_path("reset.bmp")


def jog_pad_ipc_server_name(adapter_url: str) -> str:
    digest = hashlib.sha1(adapter_url.encode("utf-8")).hexdigest()[:12]
    return f"{JOG_PAD_IPC_PREFIX}_{digest}"


def resolve_adapter_url(adapter_url: Optional[str] = None) -> str:
    """Resolve the adapter URL from CLI/env/config, in that order."""
    if adapter_url:
        return adapter_url.rstrip("/")

    env_url = os.environ.get("ERP_CNC_ADAPTER_URL")
    if env_url:
        return env_url.rstrip("/")

    repo_root = Path(__file__).resolve().parents[2]
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)

    try:
        from src.core.config import Settings

        port = int(Settings().port)
    except Exception as exc:
        print(f"Could not read adapter config port, using {FALLBACK_ADAPTER_PORT}: {exc}")
        port = FALLBACK_ADAPTER_PORT

    return f"http://127.0.0.1:{port}"


@dataclass(frozen=True)
class JogPadTheme:
    """Visual settings for the complete jog pad."""

    accent_blue: str = ACCENT_BLUE
    window_background: str = "#F1F1F1"
    panel_background: str = "#F1F1F1"
    outer_button_background: str = "#FAFAFA"
    outer_button_border: str = "#C8C8C8"
    text_color: str = "#202020"
    slider_groove: str = "#D0D0D0"

    @property
    def accent(self) -> QColor:
        return QColor(self.accent_blue)

    @property
    def accent_pressed(self) -> QColor:
        return self.accent.darker(125)

    @property
    def accent_hover(self) -> QColor:
        return self.accent.lighter(112)


THEME = JogPadTheme()

JOG_DIRECTION_ICONS = {
    "up": "jog_up.bmp",
    "down": "jog_down.bmp",
    "left": "jog_left.bmp",
    "right": "jog_right.bmp",
}

STEP_MODE_ICONS = {
    "cont": "jog_cont.bmp",
    ".001": "jog_0_001.bmp",
    "0.01": "jog_0_01.bmp",
    "0.1": "jog_0_1.bmp",
    "1": "jog_1.bmp",
}
