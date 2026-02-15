"""
ERP-CNC Adapter Installer — Custom Title Bar widget.
"""
from typing import Optional

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont, QMouseEvent

from ..constants import VERSION


class TitleBar(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)
        self._parent = parent
        self._drag_pos: Optional[QPoint] = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 8, 0)

        title = QLabel(f"ERP-CNC Adapter Setup v{VERSION}")
        title.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        lay.addWidget(title)

        lay.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(36, 30)
        close_btn.clicked.connect(self._parent.close)
        lay.addWidget(close_btn)

    # Drag support ─────────────────────────────────────────────────────────
    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPos() - self._parent.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._drag_pos and ev.buttons() & Qt.LeftButton:
            self._parent.move(ev.globalPos() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent):
        self._drag_pos = None
