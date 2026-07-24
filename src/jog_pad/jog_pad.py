"""
Standalone PyQt5 desktop jog pad.

Install:
    pip install PyQt5

Run:
    python jog_pad.py

Jog commands are sent to the running adapter over HTTP. Set
ERP_CNC_ADAPTER_URL or pass --adapter-url to use a non-default adapter URL.

The button blue is controlled by the single ACCENT_BLUE constant.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
from pathlib import Path
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QPointF, QRectF, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


# =============================================================================
# SINGLE SOURCE OF TRUTH FOR THE BLUE BUTTON COLOR
# =============================================================================

ACCENT_BLUE = "#7A4FBF"
FALLBACK_ADAPTER_PORT = 8002


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


def resolve_home_icon_path() -> Optional[str]:
    """Locate resources/home.bmp for dev and installed runs."""
    return resolve_resource_path("home.bmp")


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


class AdapterJogClient:
    """Small stdlib HTTP client for the adapter jog endpoints."""

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 2.0) -> None:
        self.base_url = resolve_adapter_url(base_url)
        self.timeout_seconds = timeout_seconds

    def start_continuous_jog(self, axis: str, direction: int, speed_percent: float) -> dict:
        return self._post_json(
            "/api/cnc/jog",
            {
                "axis": axis,
                "direction": direction,
                "step": 1.0,
                "velocity_factor": self._velocity_factor(speed_percent),
                "continuous": True,
            },
        )

    def stop_continuous_jog(self) -> dict:
        return self._post_json("/api/cnc/jog/stop", None)

    def get_positions(self) -> dict:
        return self._get_json("/api/cnc/position")

    def get_homed_status(self) -> dict:
        return self._get_json("/api/cnc/homed")

    def home_all_axes(self) -> dict:
        return self._post_json("/api/cnc/home", None)

    def pause_job(self) -> dict:
        return self._post_json("/api/cnc/job/pause", None)

    def move_relative(self, axis: str, signed_distance: float, speed_percent: float) -> dict:
        direction = 1 if signed_distance >= 0 else -1
        return self._post_json(
            "/api/cnc/jog",
            {
                "axis": axis,
                "direction": direction,
                "step": abs(float(signed_distance)),
                "velocity_factor": self._velocity_factor(speed_percent),
                "continuous": False,
            },
        )

    def zero_work_axis(self, axis: str) -> dict:
        return self._post_json("/api/cnc/zero", {"axis": axis})

    def set_work_coordinate(self, axis: str, value: float) -> dict:
        return self._post_json("/api/cnc/work-coordinate", {"axis": axis, "value": float(value)})

    def _get_json(self, path: str) -> dict:
        request = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                return {"status": response.status, "message": "No response body"}
            return json.loads(response_body)

    def _post_json(self, path: str, payload: Optional[dict]) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                return {"status": response.status, "message": "No response body"}
            return json.loads(response_body)

    @staticmethod
    def _velocity_factor(speed_percent: float) -> float:
        return max(0.01, min(1.0, float(speed_percent) / 100.0))


class BackgroundCommandSender(QObject):
    """Runs adapter HTTP calls off the Qt UI thread."""

    command_succeeded = pyqtSignal(str, str)
    command_failed = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._commands: queue.Queue[Optional[tuple[str, Callable[[], dict]]]] = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="jog-pad-http", daemon=True)
        self._worker.start()

    def submit(self, label: str, command: Callable[[], dict]) -> None:
        self._commands.put((label, command))

    def close(self) -> None:
        self._commands.put(None)

    def _run(self) -> None:
        while True:
            item = self._commands.get()
            if item is None:
                return

            label, command = item
            try:
                response = command()
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                message = f"HTTP {exc.code}: {details}"
                print(f"Adapter jog request failed: {label}: {message}")
                self.command_failed.emit(label, message)
            except Exception as exc:
                message = str(exc)
                print(f"Adapter jog request failed: {label}: {message}")
                self.command_failed.emit(label, message)
            else:
                status = response.get("status", "?")
                message = response.get("message", "")
                print(f"Adapter jog request sent: {label}: status={status}, message={message}")
                if status == 0:
                    self.command_succeeded.emit(label, message)
                else:
                    self.command_failed.emit(label, message or f"Adapter returned status {status}")

class CoordinatePoller(QThread):
    positions_received = pyqtSignal(dict)
    homed_status_received = pyqtSignal(dict)
    error_received = pyqtSignal(str)

    def __init__(self, client: AdapterJogClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.client = client
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            try:
                self.positions_received.emit(self.client.get_positions())
                self.homed_status_received.emit(self.client.get_homed_status())
            except Exception as exc:
                self.error_received.emit(str(exc))
            self.msleep(500)


class PauseHoldThread(QThread):
    error_received = pyqtSignal(str)

    def __init__(self, client: AdapterJogClient, interval_ms: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.client = client
        self.interval_ms = max(0, int(interval_ms))
        self._running = self.interval_ms > 0

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            try:
                self.client.pause_job()
            except Exception as exc:
                self.error_received.emit(str(exc))
            self.msleep(self.interval_ms)


class ArrowJogButton(QPushButton):
    """Square jog button that paints its own arrow and axis label."""

    def __init__(
        self,
        direction: str,
        label: str,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.direction = direction
        self.axis_label = label
        self.theme = theme

        self.setFixedSize(72, 68)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(f"Jog {label}")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor(self.theme.outer_button_border), 1.0))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 4.0, 4.0)

        inner_size = 48.0
        inner = QRectF(
            (self.width() - inner_size) / 2.0,
            (self.height() - inner_size) / 2.0,
            inner_size,
            inner_size,
        )

        if self.isDown():
            fill = self.theme.accent_pressed
        elif self.underMouse():
            fill = self.theme.accent_hover
        else:
            fill = self.theme.accent

        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 4.0, 4.0)

        self._draw_arrow(painter, inner)
        self._draw_label(painter, inner)

    def _draw_arrow(self, painter: QPainter, rect: QRectF) -> None:
        center = rect.center()
        length = 25.0
        head = 8.0

        if self.direction == "up":
            start = QPointF(center.x(), center.y() + length / 2.0)
            end = QPointF(center.x(), center.y() - length / 2.0)
            head_a = QPointF(end.x() - head, end.y() + head)
            head_b = QPointF(end.x() + head, end.y() + head)
        elif self.direction == "down":
            start = QPointF(center.x(), center.y() - length / 2.0)
            end = QPointF(center.x(), center.y() + length / 2.0)
            head_a = QPointF(end.x() - head, end.y() - head)
            head_b = QPointF(end.x() + head, end.y() - head)
        elif self.direction == "left":
            start = QPointF(center.x() + length / 2.0, center.y())
            end = QPointF(center.x() - length / 2.0, center.y())
            head_a = QPointF(end.x() + head, end.y() - head)
            head_b = QPointF(end.x() + head, end.y() + head)
        elif self.direction == "right":
            start = QPointF(center.x() - length / 2.0, center.y())
            end = QPointF(center.x() + length / 2.0, center.y())
            head_a = QPointF(end.x() - head, end.y() - head)
            head_b = QPointF(end.x() - head, end.y() + head)
        else:
            return

        pen = QPen(QColor("white"), 5.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(start, end)
        painter.drawLine(end, head_a)
        painter.drawLine(end, head_b)

    def _draw_label(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)

        label_rect = QRectF(
            rect.right() - 19.0,
            rect.bottom() - 16.0,
            17.0,
            14.0,
        )
        painter.drawText(
            label_rect,
            Qt.AlignCenter,
            self.axis_label,
        )


class StepModeButton(QPushButton):
    """Blue mode button with four small directional markers."""

    def __init__(
        self,
        text: str,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.mode_text = text
        self.theme = theme

        self.setCheckable(True)
        self.setFixedSize(72, 68)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        border_color = self.theme.accent if self.isChecked() else QColor(self.theme.outer_button_border)
        border_width = 2.0 if self.isChecked() else 1.0

        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 4.0, 4.0)

        inner = QRectF(12.0, 10.0, 48.0, 48.0)
        if self.isDown():
            fill = self.theme.accent_pressed
        elif self.underMouse():
            fill = self.theme.accent_hover
        else:
            fill = self.theme.accent

        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 4.0, 4.0)

        painter.setBrush(QColor("white"))
        self._draw_triangle(painter, QPointF(inner.center().x(), inner.top() + 5), "up")
        self._draw_triangle(painter, QPointF(inner.center().x(), inner.bottom() - 5), "down")
        self._draw_triangle(painter, QPointF(inner.left() + 5, inner.center().y()), "left")
        self._draw_triangle(painter, QPointF(inner.right() - 5, inner.center().y()), "right")

        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.drawText(inner, Qt.AlignCenter, self.mode_text)

    @staticmethod
    def _draw_triangle(painter: QPainter, center: QPointF, direction: str) -> None:
        size = 5.0
        path = QPainterPath()

        if direction == "up":
            path.moveTo(center.x(), center.y() - size)
            path.lineTo(center.x() - size, center.y() + size)
            path.lineTo(center.x() + size, center.y() + size)
        elif direction == "down":
            path.moveTo(center.x(), center.y() + size)
            path.lineTo(center.x() - size, center.y() - size)
            path.lineTo(center.x() + size, center.y() - size)
        elif direction == "left":
            path.moveTo(center.x() - size, center.y())
            path.lineTo(center.x() + size, center.y() - size)
            path.lineTo(center.x() + size, center.y() + size)
        else:
            path.moveTo(center.x() + size, center.y())
            path.lineTo(center.x() - size, center.y() - size)
            path.lineTo(center.x() - size, center.y() + size)

        path.closeSubpath()
        painter.drawPath(path)


class CustomStepButton(QPushButton):
    """Small horizontal-arrow button used to activate the custom step value."""

    def __init__(
        self,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setFixedSize(72, 38)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("Use the custom step value")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor(self.theme.outer_button_border), 1.0))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 4.0, 4.0)

        inner = QRectF(12.0, 7.0, 48.0, 24.0)
        fill = self.theme.accent_pressed if self.isDown() else self.theme.accent
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 3.0, 3.0)

        painter.setPen(QPen(QColor("white"), 2.5))
        y = inner.center().y()
        painter.drawLine(QPointF(inner.left() + 8, y), QPointF(inner.right() - 8, y))
        painter.drawLine(QPointF(inner.left() + 8, y), QPointF(inner.left() + 14, y - 5))
        painter.drawLine(QPointF(inner.left() + 8, y), QPointF(inner.left() + 14, y + 5))
        painter.drawLine(QPointF(inner.right() - 8, y), QPointF(inner.right() - 14, y - 5))
        painter.drawLine(QPointF(inner.right() - 8, y), QPointF(inner.right() - 14, y + 5))


class ZeroAxisButton(QPushButton):
    """Per-axis work-zero control shown beside the DRO rows."""

    def __init__(
        self,
        axis: str,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.axis = axis
        self.theme = theme
        self.setFixedSize(58, 58)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Zero work {axis}")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor(self.theme.outer_button_border), 1.0))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 3.0, 3.0)

        inner = QRectF(9.0, 8.0, 40.0, 40.0)
        fill = self.theme.accent_pressed if self.isDown() else self.theme.accent
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 4.0, 4.0)

        center = inner.center()
        painter.setPen(QPen(QColor("white"), 2.0))
        painter.drawEllipse(center, 14.0, 14.0)
        painter.drawLine(QPointF(center.x(), inner.top() + 4.0), QPointF(center.x(), inner.bottom() - 4.0))
        painter.drawLine(QPointF(inner.left() + 4.0, center.y()), QPointF(inner.right() - 4.0, center.y()))

        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(inner.right() - 15.0, inner.bottom() - 14.0, 13.0, 12.0), Qt.AlignCenter, self.axis)


class CoordinateReadout(QFrame):
    """CNC-style digital readout row for one axis."""

    clicked = pyqtSignal(str)

    def __init__(self, axis: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.axis = axis
        self.setObjectName("coordinateReadout")
        self.setFixedSize(318, 58)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Set G92 {axis}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 14, 2)
        layout.setSpacing(10)

        axis_label = QLabel(axis)
        axis_label.setObjectName("coordinateAxis")
        axis_label.setFixedWidth(44)
        axis_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.value_label = QLabel("0.000")
        self.value_label.setObjectName("coordinateValue")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout.addWidget(axis_label)
        layout.addWidget(self.value_label, 1)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.axis)
        super().mousePressEvent(event)


class HomeStatusButton(QPushButton):
    """Shows whether the CNC reports all axes are homed."""

    def __init__(self, theme: JogPadTheme = THEME, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self._homed: Optional[bool] = None
        home_icon_path = resolve_home_icon_path()
        self._home_pixmap = QPixmap(home_icon_path) if home_icon_path else QPixmap()
        self.setFixedSize(72, 68)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Run G28 X0 Y0 Z0")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def set_homed(self, homed: Optional[bool]) -> None:
        self._homed = homed
        if homed is True:
            self.setToolTip("All axes are homed. Click to run G28 X0 Y0 Z0")
        elif homed is False:
            self.setToolTip("Not all axes are homed. Click to run G28 X0 Y0 Z0")
        else:
            self.setToolTip("Homed status unavailable. Click to run G28 X0 Y0 Z0")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor(self.theme.outer_button_border), 1.0))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 4.0, 4.0)

        inner = QRectF(12.0, 10.0, 48.0, 48.0)
        if self._homed is True:
            fill = self.theme.accent
        elif self._homed is False:
            fill = QColor("#7C7C7C")
        else:
            fill = QColor("#B8B8B8")
        if self.isDown():
            fill = fill.darker(125)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 4.0, 4.0)

        if not self._home_pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._home_pixmap)
            return

        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(inner, Qt.AlignCenter, "HOME")


class CloseButton(QPushButton):
    """Large close button matching the visual language of the jog buttons."""

    def __init__(
        self,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setFixedSize(72, 68)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("Proceed")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor(self.theme.outer_button_border), 1.0))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 4.0, 4.0)

        inner = QRectF(12.0, 10.0, 48.0, 48.0)
        fill = self.theme.accent_pressed if self.isDown() else self.theme.accent
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 4.0, 4.0)

        painter.setPen(QPen(QColor("white"), 6.0, Qt.SolidLine, Qt.RoundCap))
        margin = 14.0
        painter.drawLine(
            QPointF(inner.left() + 12, inner.center().y()),
            QPointF(inner.center().x() - 3, inner.bottom() - 13),
        )
        painter.drawLine(
            QPointF(inner.center().x() - 3, inner.bottom() - 13),
            QPointF(inner.right() - 11, inner.top() + 13),
        )


class JogPad(QWidget):
    """
    Jog pad widget.

    Signals are supplied in addition to the editable action methods, so the
    widget can be integrated without changing its UI code.
    """

    jog_started = pyqtSignal(str, int, float)
    jog_stopped = pyqtSignal(str)
    step_requested = pyqtSignal(str, float, float)
    speed_changed = pyqtSignal(float)
    mode_changed = pyqtSignal(object)

    CONTINUOUS = None

    def __init__(
        self,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
        adapter_url: Optional[str] = None,
        pause_hold_interval_ms: int = 500,
    ) -> None:

        super().__init__(parent)
        self.theme = theme
        self.adapter_client = AdapterJogClient(adapter_url)
        self.command_sender = BackgroundCommandSender(self)
        self.command_sender.command_succeeded.connect(self.on_command_succeeded)
        self.command_sender.command_failed.connect(self.on_command_failed)
        self.coordinate_labels: dict[str, QLabel] = {}
        self.coordinate_readouts: dict[str, CoordinateReadout] = {}
        self.coordinate_mode = "work"
        self.coordinate_mode_buttons: dict[str, QPushButton] = {}
        self.latest_positions: dict = {}
        self.position_poller = CoordinatePoller(self.adapter_client, self)
        self.position_poller.positions_received.connect(self.on_positions_received)
        self.position_poller.homed_status_received.connect(self.on_homed_status_received)
        self.position_poller.error_received.connect(self.on_position_error)
        self.position_poller.start()
        self.pause_hold_thread = PauseHoldThread(self.adapter_client, pause_hold_interval_ms, self)
        self.pause_hold_thread.error_received.connect(self.on_pause_hold_error)
        if pause_hold_interval_ms > 0:
            self.pause_hold_thread.start()
        self.selected_step: Optional[float] = self.CONTINUOUS
        self._active_axis: Optional[str] = None

        self.setObjectName("jogPad")
        self.setMinimumSize(1060, 470)
        self._build_ui()
        self._connect_actions()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 10)
        root.setSpacing(18)

        motion_row = QHBoxLayout()
        motion_row.setSpacing(26)

        xy_panel = self._build_xy_panel()
        z_panel = self._build_z_panel()

        motion_row.addWidget(xy_panel, 0, Qt.AlignTop)
        motion_row.addWidget(z_panel, 0, Qt.AlignTop)
        motion_row.addSpacing(54)
        motion_row.addWidget(self._build_coordinate_panel(), 0, Qt.AlignTop)
        motion_row.addStretch(1)
        root.addLayout(motion_row)

        root.addSpacing(6)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 100)
        self.speed_slider.setValue(10)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.setPageStep(5)
        self.speed_slider.setMaximumWidth(632)
        self.speed_slider.setToolTip("Jog speed: 10%")
        root.addWidget(self.speed_slider)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        self.mode_label = QLabel("Cont")
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setFixedSize(64, 28)
        self.mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_row.addWidget(self.mode_label)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumSize(520, 28)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        root.addLayout(status_row)

        root.addStretch(1)
        root.addLayout(self._build_bottom_controls())

    def _build_coordinate_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("coordinatePanel")
        panel.setFixedWidth(390)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        for mode, label in (("machine", "Machine"), ("work", "Work")):
            button = QPushButton(label)
            button.setObjectName("coordinateModeTab")
            button.setCheckable(True)
            button.setChecked(mode == self.coordinate_mode)
            button.setFixedSize(82, 24)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda checked=False, selected=mode: self.set_coordinate_mode(selected))
            self.coordinate_mode_buttons[mode] = button
            tab_row.addWidget(button)
        tab_row.addStretch(1)
        layout.addLayout(tab_row)

        for axis in ("X", "Y", "Z"):
            row = QHBoxLayout()
            row.setSpacing(8)
            zero_button = ZeroAxisButton(axis, self.theme)
            readout = CoordinateReadout(axis)
            self.coordinate_labels[axis.lower()] = readout.value_label
            self.coordinate_readouts[axis.lower()] = readout
            zero_button.clicked.connect(lambda checked=False, selected=axis: self.action_zero_work_axis(selected))
            readout.clicked.connect(self.show_work_coordinate_dialog)
            row.addWidget(zero_button)
            row.addWidget(readout)
            layout.addLayout(row)

        return panel

    def _build_xy_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addSpacing(86)
        self.y_positive_button = ArrowJogButton("up", "Y+", self.theme)
        top.addWidget(self.y_positive_button)
        top.addStretch(1)

        middle = QHBoxLayout()
        self.x_negative_button = ArrowJogButton("left", "X-", self.theme)
        self.x_positive_button = ArrowJogButton("right", "X+", self.theme)
        middle.addWidget(self.x_negative_button)
        middle.addSpacing(100)
        middle.addWidget(self.x_positive_button)

        bottom = QHBoxLayout()
        bottom.addSpacing(86)
        self.y_negative_button = ArrowJogButton("down", "Y-", self.theme)
        bottom.addWidget(self.y_negative_button)
        bottom.addStretch(1)

        layout.addLayout(top)
        layout.addLayout(middle)
        layout.addLayout(bottom)
        return panel

    def _build_z_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(88)

        self.z_positive_button = ArrowJogButton("up", "Z+", self.theme)
        self.z_negative_button = ArrowJogButton("down", "Z-", self.theme)

        layout.addWidget(self.z_positive_button)
        layout.addWidget(self.z_negative_button)
        return panel

    def _build_bottom_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.continuous_button = StepModeButton("cont", self.theme)
        self.step_0001_button = StepModeButton(".001", self.theme)
        self.step_001_button = StepModeButton("0.01", self.theme)
        self.step_01_button = StepModeButton("0.1", self.theme)
        self.step_1_button = StepModeButton("1", self.theme)
        self.home_button = HomeStatusButton(self.theme)

        mode_buttons = (
            self.continuous_button,
            self.step_0001_button,
            self.step_001_button,
            self.step_01_button,
            self.step_1_button,
        )
        for button in mode_buttons:
            self.mode_group.addButton(button)

        self.continuous_button.setChecked(True)

        row.addWidget(self.continuous_button)
        row.addSpacerItem(QSpacerItem(86, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        row.addWidget(self.step_0001_button)
        row.addWidget(self.step_001_button)
        row.addWidget(self.step_01_button)
        row.addWidget(self.step_1_button)
        row.addWidget(self.home_button)

        custom_column = QVBoxLayout()
        custom_column.setSpacing(4)

        self.custom_step_edit = QLineEdit("5.0")
        self.custom_step_edit.setFixedSize(72, 28)
        self.custom_step_edit.setToolTip("Custom step distance")
        self.custom_step_button = CustomStepButton(self.theme)

        custom_column.addWidget(self.custom_step_edit)
        custom_column.addWidget(self.custom_step_button)
        row.addLayout(custom_column)

        row.addStretch(1)

        self.close_button = CloseButton(self.theme)
        row.addWidget(self.close_button)
        return row

    def _connect_actions(self) -> None:
        # Direction buttons. Each connection points to a clearly named method.
        self.x_positive_button.pressed.connect(self.on_x_positive_pressed)
        self.x_positive_button.released.connect(self.on_x_positive_released)

        self.x_negative_button.pressed.connect(self.on_x_negative_pressed)
        self.x_negative_button.released.connect(self.on_x_negative_released)

        self.y_positive_button.pressed.connect(self.on_y_positive_pressed)
        self.y_positive_button.released.connect(self.on_y_positive_released)

        self.y_negative_button.pressed.connect(self.on_y_negative_pressed)
        self.y_negative_button.released.connect(self.on_y_negative_released)

        self.z_positive_button.pressed.connect(self.on_z_positive_pressed)
        self.z_positive_button.released.connect(self.on_z_positive_released)

        self.z_negative_button.pressed.connect(self.on_z_negative_pressed)
        self.z_negative_button.released.connect(self.on_z_negative_released)

        # Jog mode buttons.
        self.continuous_button.clicked.connect(
            lambda: self.set_jog_mode(self.CONTINUOUS, "Cont")
        )
        self.step_0001_button.clicked.connect(lambda: self.set_jog_mode(0.001, "0.001"))
        self.step_001_button.clicked.connect(lambda: self.set_jog_mode(0.01, "0.01"))
        self.step_01_button.clicked.connect(lambda: self.set_jog_mode(0.1, "0.1"))
        self.step_1_button.clicked.connect(lambda: self.set_jog_mode(1.0, "1.0"))

        self.custom_step_button.clicked.connect(self.use_custom_step)
        self.custom_step_edit.returnPressed.connect(self.use_custom_step)

        self.speed_slider.valueChanged.connect(self.on_speed_slider_changed)
        self.home_button.clicked.connect(self.action_home_all_axes)
        self.close_button.clicked.connect(self.on_close_pressed)

    def _apply_style(self) -> None:
        accent = self.theme.accent_blue
        accent_pressed = self.theme.accent_pressed.name()
        background = self.theme.window_background

        self.setStyleSheet(
            f"""
            QWidget#jogPad {{
                background: {background};
                color: {self.theme.text_color};
                font-family: "Segoe UI";
                font-size: 12px;
            }}

            QLabel#modeLabel {{
                background: white;
                border: 1px solid #C8C8C8;
                padding-left: 3px;
            }}

            QLabel#statusLabel {{
                background: white;
                border: 1px solid #C8C8C8;
                color: #202020;
                padding-left: 8px;
                padding-right: 8px;
            }}

            QWidget#coordinatePanel {{
                background: #F1F1F1;
            }}

            QPushButton#coordinateModeTab {{
                background: #E8E8E8;
                border: 1px solid #B6B6B6;
                border-bottom: none;
                color: #111111;
                font-size: 12px;
                padding: 1px 8px;
            }}

            QPushButton#coordinateModeTab:checked {{
                background: white;
            }}

            QFrame#coordinateReadout {{
                background: {accent};
                border-top: 2px solid #101010;
                border-left: 2px solid #101010;
                border-right: 2px solid #8FA6D2;
                border-bottom: 2px solid #8FA6D2;
            }}

            QLabel#coordinateAxis {{
                color: white;
                font-family: "Times New Roman";
                font-size: 38px;
            }}

            QLabel#coordinateValue {{
                color: white;
                font-family: "Times New Roman";
                font-size: 40px;
            }}

            QLineEdit {{
                background: white;
                border: 1px solid #D5DDE9;
                selection-background-color: {accent};
                font-size: 12px;
            }}

            QSlider::groove:horizontal {{
                height: 4px;
                background: {self.theme.slider_groove};
                border: 1px solid #C3C3C3;
            }}

            QSlider::sub-page:horizontal {{
                background: {accent};
                border: none;
            }}

            QSlider::handle:horizontal {{
                width: 14px;
                margin: -8px 0;
                background: {accent};
                border: none;
            }}

            QSlider::handle:horizontal:pressed {{
                background: {accent_pressed};
            }}
            """
        )

    @property
    def speed_percent(self) -> float:
        return float(self.speed_slider.value())

    # =========================================================================
    # BUTTON-SPECIFIC ACTION METHODS
    #
    # These are intentionally separate so any individual button behavior can
    # be changed without touching the layout or painting code.
    # =========================================================================

    def on_x_positive_pressed(self) -> None:
        self._jog_pressed("X", +1)

    def on_x_positive_released(self) -> None:
        self._jog_released("X")

    def on_x_negative_pressed(self) -> None:
        self._jog_pressed("X", -1)

    def on_x_negative_released(self) -> None:
        self._jog_released("X")

    def on_y_positive_pressed(self) -> None:
        self._jog_pressed("Y", +1)

    def on_y_positive_released(self) -> None:
        self._jog_released("Y")

    def on_y_negative_pressed(self) -> None:
        self._jog_pressed("Y", -1)

    def on_y_negative_released(self) -> None:
        self._jog_released("Y")

    def on_z_positive_pressed(self) -> None:
        self._jog_pressed("Z", +1)

    def on_z_positive_released(self) -> None:
        self._jog_released("Z")

    def on_z_negative_pressed(self) -> None:
        self._jog_pressed("Z", -1)

    def on_z_negative_released(self) -> None:
        self._jog_released("Z")

    def on_close_pressed(self) -> None:
        self.window().close()

    def show_work_coordinate_dialog(self, axis: str) -> None:
        if self.coordinate_mode != "work":
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"G92 {axis}")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        field_row = QHBoxLayout()
        label = QLabel(f"G92{axis}")
        label.setObjectName("g92Label")
        label.setFixedWidth(62)
        value_edit = QLineEdit(self._current_coordinate_text(axis))
        value_edit.setObjectName("g92ValueEdit")
        value_edit.setFixedWidth(120)
        value_edit.selectAll()
        field_row.addWidget(label)
        field_row.addWidget(value_edit)
        layout.addLayout(field_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.setFixedWidth(74)
        cancel_button.setFixedWidth(74)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            value = float(value_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid G92 value", "Enter a valid numeric coordinate value.")
            return

        self.action_set_work_coordinate(axis, value)

    def _current_coordinate_text(self, axis: str) -> str:
        coordinates = self.latest_positions.get("work") or {}
        value = coordinates.get(axis.lower())
        if value is None:
            return "0.000"
        return f"{float(value):.3f}"

    def on_positions_received(self, payload: dict) -> None:
        self.latest_positions = payload
        self._update_coordinate_labels()

    def on_position_error(self, message: str) -> None:
        for axis in ("x", "y", "z"):
            self.coordinate_labels[axis].setText("---.---")
        self.set_status(f"Position read failed: {message}", error=True)

    def on_command_succeeded(self, label: str, message: str) -> None:
        self.set_status(f"{label}: {message or 'OK'}", error=False)

    def on_command_failed(self, label: str, message: str) -> None:
        self.set_status(f"{label}: {message}", error=True)

    def set_status(self, message: str, error: bool = False) -> None:
        self.status_label.setText(message)
        color = "#B00020" if error else "#146C2E"
        self.status_label.setStyleSheet(f"color: {color};")

    def on_pause_hold_error(self, message: str) -> None:
        print(f"Adapter pause hold failed: {message}")
        self.set_status(f"Pause hold failed: {message}", error=True)

    def on_homed_status_received(self, payload: dict) -> None:
        self.home_button.set_homed(bool(payload.get("allAxesHomed")))

    def set_coordinate_mode(self, mode: str) -> None:
        if mode not in ("work", "machine"):
            return
        self.coordinate_mode = mode
        for button_mode, button in self.coordinate_mode_buttons.items():
            button.setChecked(button_mode == mode)
        for axis, readout in self.coordinate_readouts.items():
            readout.setToolTip(f"Set G92 {axis.upper()}" if mode == "work" else "Machine coordinates are read-only")
            readout.setCursor(Qt.PointingHandCursor if mode == "work" else Qt.ArrowCursor)
        self._update_coordinate_labels()

    def _update_coordinate_labels(self) -> None:
        coordinates = self.latest_positions.get(self.coordinate_mode) or {}
        for axis in ("x", "y", "z"):
            value = coordinates.get(axis)
            if value is None:
                self.coordinate_labels[axis].setText("---.---")
                continue
            self.coordinate_labels[axis].setText(f"{float(value):.3f}")

    def on_speed_slider_changed(self, value: int) -> None:
        self.speed_slider.setToolTip(f"Jog speed: {value}%")
        self.speed_changed.emit(float(value))
        self.action_speed_changed(float(value))

    def set_jog_mode(self, step: Optional[float], display_text: str) -> None:
        self.selected_step = step
        self.mode_label.setText(display_text)
        self.mode_changed.emit(step)
        self.action_mode_changed(step)

    def use_custom_step(self) -> None:
        try:
            step = float(self.custom_step_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid step", "Enter a valid numeric step value.")
            self.custom_step_edit.setFocus()
            self.custom_step_edit.selectAll()
            return

        if step <= 0:
            QMessageBox.warning(self, "Invalid step", "The step value must be greater than zero.")
            self.custom_step_edit.setFocus()
            self.custom_step_edit.selectAll()
            return

        self.mode_group.setExclusive(False)
        for button in self.mode_group.buttons():
            button.setChecked(False)
        self.mode_group.setExclusive(True)

        self.set_jog_mode(step, f"{step:g}")

    def _jog_pressed(self, axis: str, direction: int) -> None:
        if self.selected_step is self.CONTINUOUS:
            self._active_axis = axis
            self.jog_started.emit(axis, direction, self.speed_percent)
            self.action_start_continuous_jog(axis, direction, self.speed_percent)
            return

        signed_distance = float(direction) * float(self.selected_step)
        self.step_requested.emit(axis, signed_distance, self.speed_percent)
        self.action_move_relative(axis, signed_distance, self.speed_percent)

    def _jog_released(self, axis: str) -> None:
        if self.selected_step is not self.CONTINUOUS:
            return

        if self._active_axis == axis:
            self._active_axis = None
            self.jog_stopped.emit(axis)
            self.action_stop_continuous_jog(axis)

    # =========================================================================
    # ADAPTER HTTP ACTIONS
    #
    # These methods send commands to the running adapter over localhost HTTP.
    # =========================================================================

    def action_start_continuous_jog(
        self,
        axis: str,
        direction: int,
        speed_percent: float,
    ) -> None:
        """Called once when a direction button is pressed in continuous mode."""
        sign = "+" if direction > 0 else "-"
        self.command_sender.submit(
            f"start {axis}{sign}",
            lambda: self.adapter_client.start_continuous_jog(axis, direction, speed_percent),
        )

    def action_stop_continuous_jog(self, axis: str) -> None:
        """Called when a continuous-jog direction button is released."""
        self.command_sender.submit(
            f"stop {axis}",
            self.adapter_client.stop_continuous_jog,
        )

    def action_move_relative(
        self,
        axis: str,
        signed_distance: float,
        speed_percent: float,
    ) -> None:
        """Called once for every press while a fixed step mode is selected."""
        self.command_sender.submit(
            f"step {axis} {signed_distance:g}",
            lambda: self.adapter_client.move_relative(axis, signed_distance, speed_percent),
        )

    def action_zero_work_axis(self, axis: str) -> None:
        """Set the current position as work zero for one axis."""
        self.command_sender.submit(
            f"zero {axis}",
            lambda: self.adapter_client.zero_work_axis(axis),
        )

    def action_set_work_coordinate(self, axis: str, value: float) -> None:
        """Set the displayed work coordinate value for one axis."""
        self.command_sender.submit(
            f"G92 {axis}{value:g}",
            lambda: self.adapter_client.set_work_coordinate(axis, value),
        )

    def action_home_all_axes(self) -> None:
        """Run the all-axis home MDI command."""
        self.command_sender.submit(
            "home G28 X0 Y0 Z0",
            self.adapter_client.home_all_axes,
        )

    def action_speed_changed(self, speed_percent: float) -> None:
        """Called whenever the speed slider changes."""
        print(f"SPEED changed: {speed_percent:.0f}%")

    def action_mode_changed(self, step: Optional[float]) -> None:
        """Called when continuous or fixed-step mode changes."""
        if step is None:
            print("MODE changed: continuous")
        else:
            print(f"MODE changed: step={step:g}")


class JogPadWindow(QMainWindow):
    def __init__(self, adapter_url: Optional[str] = None, pause_hold_interval_ms: int = 500) -> None:
        super().__init__()
        self.setWindowTitle("Jog Pad")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        icon_path = resolve_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1165, 497)
        self.setMinimumSize(1060, 470)
        self.jog_pad = JogPad(adapter_url=adapter_url, pause_hold_interval_ms=pause_hold_interval_ms)
        self.setCentralWidget(self.jog_pad)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.jog_pad.pause_hold_thread.stop()
        self.jog_pad.pause_hold_thread.wait(1000)
        self.jog_pad.position_poller.stop()
        self.jog_pad.position_poller.wait(1000)
        self.jog_pad.command_sender.close()
        super().closeEvent(event)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ERP CNC Adapter jog pad")
    parser.add_argument(
        "--adapter-url",
        default=None,
        help="Base URL for the running adapter. Defaults to ERP_CNC_ADAPTER_URL or the configured adapter port.",
    )
    parser.add_argument(
        "--pause-hold-interval-ms",
        type=int,
        default=500,
        help="Milliseconds between pause requests while the jog pad is open. Use 0 to disable.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args(sys.argv[1:])

    app = QApplication(sys.argv)
    app.setApplicationName("Jog Pad")
    icon_path = resolve_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    app.setStyle("Fusion")

    window = JogPadWindow(adapter_url=args.adapter_url, pause_hold_interval_ms=args.pause_hold_interval_ms)
    window.show()
    window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
    window.raise_()
    window.activateWindow()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
