from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from .config import (
    JOG_DIRECTION_ICONS,
    STEP_MODE_ICONS,
    THEME,
    JogPadTheme,
    resolve_home_icon_path,
    resolve_jogpad_icon_path,
)


class ArrowJogButton(QPushButton):
    """Square jog button that paints its own arrow and axis label."""

    def __init__(
        self,
        direction: str,
        label: str,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
        icon_name: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.direction = direction
        self.axis_label = label
        self.theme = theme
        icon_path = resolve_jogpad_icon_path(icon_name or JOG_DIRECTION_ICONS.get(direction, ""))
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()

        self.setFixedSize(72, 68)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self._touch_active = False
        self.setToolTip(f"Jog {label}")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def event(self, event) -> bool:  # noqa: A003, N802 - Qt naming
        if event.type() == QEvent.TouchBegin:
            if not self._touch_active:
                self._touch_active = True
                self.setDown(True)
                self.pressed.emit()
                self.update()
            event.accept()
            return True

        if event.type() in (QEvent.TouchEnd, QEvent.TouchCancel):
            if self._touch_active:
                self._touch_active = False
                self.setDown(False)
                self.released.emit()
                self.update()
            event.accept()
            return True

        return super().event(event)

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

        if not self._pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._pixmap)
            return

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
        icon_path = resolve_jogpad_icon_path(STEP_MODE_ICONS.get(text, ""))
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()

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

        if not self._pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._pixmap)
            return

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
        icon_path = resolve_jogpad_icon_path("jog_user.bmp")
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()
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

        if not self._pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._pixmap)
            return

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
        icon_path = resolve_jogpad_icon_path(f"home_{axis.lower()}.bmp")
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()
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

        inner = QRectF(5.0, 5.0, 48.0, 48.0)
        fill = self.theme.accent_pressed if self.isDown() else self.theme.accent
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(inner, 4.0, 4.0)

        if not self._pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._pixmap)
            return

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
    """Always-active home command button."""

    def __init__(self, theme: JogPadTheme = THEME, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.theme = theme
        home_icon_path = resolve_home_icon_path()
        self._home_pixmap = QPixmap(home_icon_path) if home_icon_path else QPixmap()
        self.setFixedSize(72, 68)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Run home sequence")
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor(self.theme.outer_button_border), 1.0))
        painter.setBrush(QColor(self.theme.outer_button_background))
        painter.drawRoundedRect(outer, 4.0, 4.0)

        inner = QRectF(12.0, 10.0, 48.0, 48.0)
        fill = self.theme.accent
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


class BitmapCommandButton(QPushButton):
    """Generic command button that paints a provided bitmap resource."""

    def __init__(
        self,
        tooltip: str,
        icon_path: Optional[str],
        fallback_text: str,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.fallback_text = fallback_text
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()
        self.setFixedSize(72, 68)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
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

        if not self._pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._pixmap)
            return

        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(inner, Qt.AlignCenter, self.fallback_text)


class CloseButton(QPushButton):
    """Large close button matching the visual language of the jog buttons."""

    def __init__(
        self,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        icon_path = resolve_jogpad_icon_path("exit.bmp")
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()
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

        if not self._pixmap.isNull():
            painter.drawPixmap(inner.toRect(), self._pixmap)
            return

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
